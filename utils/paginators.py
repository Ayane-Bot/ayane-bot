import discord
from discord.ext import commands, menus

import os

from utils.constants import DomainBaseURL
from utils.exceptions import NotAuthorized, LimitReached, UserBlacklisted


def getcustomid():
    return f"Ayane_{os.urandom(32).hex()}_authorcheck"


class BaseSource(menus.ListPageSource):
    """Subclassing to change the way some method where coded
    (ex: get_max_pages not giving 'current' max pages)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def format_page(self, menu, entries):
        return entries

    def is_paginating(self):
        return len(self.entries) > 1

    def get_max_pages(self):
        pages, left_over = divmod(len(self.entries), self.per_page)
        if left_over:
            pages += 1
        self._max_pages = pages
        return self._max_pages


class ImageSource(BaseSource):
    def __init__(
            self,
            image_info,
            user=None,
            request_time=None,
            title="Not Assigned",
            **kwargs,
    ):
        self.image_info = image_info
        self.title = title
        self.user = user
        self.request_time = request_time
        self.many = len(self.image_info) > 1
        embed_source = self.format_embeds()
        super().__init__(embed_source, **kwargs)

    def remove(self, index):
        """remove a picture from the image source and re-format the embeds to display"""
        del self.image_info[index]
        self.many = len(self.image_info) > 1
        self.entries = self.format_embeds()

    def get_infos(self, index):
        return self.image_info[index]

    def format_embeds(self):
        embed_list = []
        for i, im in enumerate(self.image_info):
            embed = discord.Embed(
                url=im["url"], colour=int(im["dominant_color"].replace("#", ""), 16)
            )
            embed.set_author(
                name=self.title,
                url=f"https://{DomainBaseURL}/preview/?image=" + im["file"] + im["extension"],
            )
            embed.set_image(url=im["url"])
            text = f"Requested by {self.user.name}"
            if self.request_time:
                text += f" | {self.request_time}s"
            if self.many:
                text += f" | {i + 1}/{len(self.image_info)}"

            embed.set_footer(text=text, icon_url=self.user.display_avatar.url)
            embed_list.append(embed)
        return embed_list

class BaseView(discord.ui.View):
        def __init__(
                self,
                ctx=None,
                delete_after=True,
                ephemeral=False,
                check_embeds=True,
                main_interaction=None,
                **kwargs,
        ):
            super().__init__(**kwargs)
            if not ctx:
                raise TypeError("ctx is a required argument")
            self.ctx: commands.Context = ctx
            self.bot = self.ctx.bot
            self.delete_after = delete_after
            self.check_embeds = check_embeds
            self.asked_for_ephemeral = ephemeral
            self.main_interaction = (
                main_interaction if main_interaction else self.ctx.interaction
            )
            self.ephemeral = ephemeral if self.main_interaction else False
            self.lock = None
            self.message = None

        def init_custom_id(self):
            for child in self.children:
                if child.custom_id == "True":
                    child.custom_id = getcustomid()

        async def stop_paginator(self, timed_out=False):
            if (timed_out and not self.delete_after and self.message) or self.ephemeral:
                for it in self.children:
                    it.disabled = True
                try:
                    if not self.ephemeral:
                        await self.message.edit(view=self)
                    else:
                        await self.main_interaction.edit_original_message(view=None)
                except:
                    pass
            self.stop()
            try:
                if (self.delete_after or not timed_out) and not self.ephemeral:
                    await self.message.delete()
                await self.ctx.message.add_reaction("<:verified_purple:840584369294671902>")
            except:
                pass

        async def interaction_check(self, interaction):
            await self.bot.is_not_blacklisted(interaction.user)
            custom_id = str(interaction.data.get("custom_id"))
            if (
                    custom_id.endswith("authorcheck")
                    and interaction.user
                    and interaction.user.id
                    not in {
                self.bot.owner_id,
                self.ctx.author.id,
                *self.bot.owner_ids,
            }
            ):
                raise NotAuthorized(self.ctx.author)
            return True

        async def send_view(self, *args, **kwargs):

            if self.main_interaction and self.main_interaction.response.is_done():
                return await self.main_interaction.edit_original_message(
                    *args, **kwargs, view=self
                )
            elif self.main_interaction:
                await self.main_interaction.response.send_message(
                    *args, **kwargs, ephemeral=self.ephemeral, view=self
                )
                return await self.main_interaction.original_message()

            ref = (
                self.ctx.message.reference.resolved if self.ctx.message.reference else None
            )
            if ref:
                if isinstance(ref, discord.DeletedReferencedMessage):
                    ref = None
            return (
                await self.ctx.send(*args, **kwargs, view=self)
                if not ref
                else await ref.reply(*args, **kwargs, view=self)
            )

        async def on_timeout(self):
            await self.stop_paginator(timed_out=True)

        async def on_error(
                self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction
        ):
            send_error_message=self.bot.get_cog("events").send_interaction_error_message
            send_unexpected_error=self.bot.get_cog("events").send_unexpected_error
            if isinstance(error, NotAuthorized):
                return await send_error_message(self.ctx, str(error),interaction=interaction, ephemeral=True)
            elif isinstance(error, LimitReached):
                await send_error_message(
                    interaction,
                    embed=discord.Embed(
                        title="🛑 LimitReached",
                        description=f"Sorry **{error.user.name}**, you already have reached the limit of **{error.limit}** "
                                    f"clicks, you are currently at **{error.counter}**, therefore I cannot process this button.",
                    ),
                    ephemeral=True,
                )
            elif isinstance(error, discord.ext.commands.NotOwner):
                embed = discord.Embed(
                    title="🛑 Owner-only",
                    description=f"Sorry **{interaction.user}**, but this command is an owner-only command and "
                                f"you arent one of my loved developers <:ty:833356132075700254>."
                )
                await send_error_message(
                    interaction, embed=embed, ephemeral=True
                )
            elif isinstance(error, UserBlacklisted):
                embed = discord.Embed(title="🛑 Forbidden", description=str(error))
                await send_error_message(
                    interaction, embed=embed, ephemeral=True
                )
            else:
                await send_unexpected_error(self.ctx,error,user=interaction.user,interaction=interaction)




