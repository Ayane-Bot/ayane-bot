import time
import waifuim
import os

import discord
from discord.ext import menus

from utils.constants import APIDomainName
from utils.modals import ReportModal, PagePrompterModal
from utils.exceptions import NotAuthorized, LimitReached, UserBlacklisted, NotOwner


def get_custom_id():
    return f"Ayane_{os.urandom(32).hex()}_author_check"


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
            *,
            title,
            image_info,
            user=None,
            request_time=None,
            **kwargs,
    ):
        self.image_info = image_info if hasattr(image_info,'__iter__') else [image_info]
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
                url=im.url, colour=int(im.dominant_color.replace("#", ""), 16)
            )
            embed.set_author(
                name=self.title,
                url=im.preview_url,
            )
            embed.set_image(url=im.url)
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
            *,
            main_interaction,
            delete_after=True,
            ephemeral=False,
            check_embeds=False,
            timeout=840,
            **kwargs,
    ):
        super().__init__(timeout=timeout, **kwargs)
        self.main_interaction = main_interaction
        self.bot = self.main_interaction.client
        self.delete_after = delete_after
        self.check_embeds = check_embeds
        self.asked_for_ephemeral = ephemeral
        self.ephemeral = ephemeral
        self.lock = None
        self.message = None
        self.no_author_check = []

    async def _scheduled_task(self, item, interaction):
        try:
            if self.timeout:
                self.__timeout_expiry = time.monotonic() + self.timeout
            if self.main_interaction.is_expired():
                return
            allow = await self.interaction_check(interaction)
            if not allow:
                return
            await item.callback(interaction)
            if not interaction.response.is_done():
                await interaction.response.defer()

        except Exception as e:
            return await self.on_error(e, item, interaction)

    async def stop_paginator(self, timed_out=False):
        if (timed_out and not self.delete_after and self.message) or self.ephemeral:
            for it in self.children:
                it.disabled = True
            try:
                if not self.ephemeral:
                    await self.message.edit(view=self)
                else:
                    await self.main_interaction.edit_original_message(view=None)
            except discord.DiscordException:
                pass
        self.stop()
        try:
            if (self.delete_after or not timed_out) and not self.ephemeral:
                await self.message.delete()
        except discord.DiscordException:
            pass

    def init_custom_id(self):
        for child in self.children:
            if child.custom_id == "True":
                child.custom_id = get_custom_id()

    async def interaction_check(self, interaction):
        reason = await self.bot.is_blacklisted(interaction.user)
        if reason:
            raise UserBlacklisted(interaction.user, reason=reason[0])
        custom_id = str(interaction.data.get("custom_id"))
        if (
                custom_id.endswith("author_check")
                and interaction.user
                and interaction.user.id
                not in {
            self.bot.owner_id,
            self.main_interaction.user.id,
            *self.bot.owner_ids,
        }
        ):
            raise NotAuthorized(self.main_interaction.user)
        return True

    async def send_message(self, *args, **kwargs):
        if self.main_interaction.response.is_done():
            return await self.main_interaction.followup.send(*args, **kwargs)
        await self.main_interaction.response.send_message(*args, **kwargs)
        return await self.main_interaction.original_message()

    async def send_view(self, *args, **kwargs):
        self.init_custom_id()
        return await self.send_message(*args, **kwargs, ephemeral=self.ephemeral, view=self)

    async def on_timeout(self):
        await self.stop_paginator(timed_out=True)

    async def on_error(
            self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction
    ):
        if isinstance(error, NotAuthorized):
            return await self.bot.send_interaction_error_message(interaction, str(error), ephemeral=True)
        elif isinstance(error, LimitReached):
            await self.bot.send_interaction_error_message(
                interaction,
                embed=discord.Embed(
                    title="🛑 LimitReached",
                    colour=self.bot.colour,
                    description=f"Sorry **{error.user.name}**,"
                                f"you already have reached the limit of **{error.limit}** "
                                f"clicks, you are currently at **{error.counter}**,"
                                "therefore I cannot process this button.",
                ),
                ephemeral=True,
            )
        elif isinstance(error, NotOwner):
            embed = discord.Embed(
                title="🛑 Owner-only",
                colour=self.bot.colour,
                description=f"Sorry **{interaction.user}**, but this command is an owner-only command and "
                            f"you arent one of my loved developers <:ty:833356132075700254>."
            )
            await self.bot.send_interaction_error_message(interaction, embed=embed, ephemeral=True)
        elif isinstance(error, UserBlacklisted):
            embed = discord.Embed(title="🛑 Forbidden", colour=self.bot.colour, description=str(error))
            await self.bot.send_interaction_error_message(interaction, embed=embed, ephemeral=True)
        else:
            await self.bot.send_unexpected_error(interaction, error, ephemeral=True)


class ViewMenu(BaseView):
    def __init__(
            self,
            *,
            source,
            is_image_menu=None,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.source = source
        self.is_image_menu = is_image_menu
        self.image_info = None
        self.source = source
        self.message = None
        self.current_page: int = 0
        self.clear_items()
        self.add_all_items()

    def update_items(self, page_number: int) -> None:
        if not self.source.is_paginating():
            self.remove_item(self.go_to_first_page)
            self.remove_item(self.go_to_previous_page)
            self.remove_item(self.go_to_next_page)
            self.remove_item(self.go_to_last_page)
            self.remove_item(self.numbered_page)
            return
        self.go_to_first_page.disabled = page_number == 0
        self.go_to_previous_page.disabled = page_number == 0
        self.go_to_next_page.disabled = page_number == self.source.get_max_pages() - 1
        self.go_to_last_page.disabled = page_number == self.source.get_max_pages() - 1

    def add_all_items(self) -> None:
        self.numbered_page.row = 1
        self.stop_pages.row = 1
        if self.source.is_paginating():
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)
            self.add_item(self.go_to_previous_page)

            self.add_item(self.go_to_next_page)
            if use_last_and_first:
                self.add_item(self.go_to_last_page)
            if not self.is_image_menu:
                self.add_item(self.stop_pages)
            self.add_item(self.numbered_page)

    async def _get_kwargs_from_page(self, page: int):
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if self.is_image_menu:
            self.image_info = self.source.get_infos(self.current_page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {"content": value, "embed": None}
        elif isinstance(value, discord.Embed):
            return {"embed": value, "content": None}
        else:
            return {}

    async def show_page(self, page_number: int
                        ) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self.update_items(page_number)

        if kwargs:
            if self.ephemeral:
                await self.main_interaction.edit_original_message(**kwargs, view=self)
                self.message = await self.main_interaction.original_message()
            else:
                self.message = await self.message.edit(**kwargs, view=self)

    async def show_checked_page(
            self, page_number: int
    ):
        max_page = self.source.get_max_pages()
        try:
            if max_page is None:
                await self.show_page(page_number)
            elif page_number >= max_page:
                await self.show_page(max_page - 1)
            elif page_number < 0:
                await self.show_page(0)
            elif max_page > page_number >= 0:
                await self.show_page(page_number)
        except IndexError:
            pass

    async def start(self):
        if (
                self.check_embeds and self.main_interaction.guild
                and not self.main_interaction.channel.permissions_for(self.main_interaction.guild.me).embed_links
        ):
            await self.send_message("Bot does not have embed links permission in this channel.")
            return
        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self.update_items(0)
        self.message = await self.send_view(**kwargs)

    @discord.ui.button(
        emoji="<:first_track:840584439830544434>",
        style=discord.ButtonStyle.grey,
        custom_id="True",
    )
    async def go_to_first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the first page"""
        await self.show_page(0)

    @discord.ui.button(
        emoji="<:before_track:840584439817699348>",
        style=discord.ButtonStyle.grey,
        custom_id="True",
    )
    async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the previous page"""
        await self.show_checked_page(self.current_page - 1)

    @discord.ui.button(
        row=1,
        emoji="<:stop_track:840584439825825802>",
        style=discord.ButtonStyle.grey,
        custom_id="True",
    )
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """stops the pagination session."""
        if self.lock and self.lock.locked():
            await interaction.response.send_message(
                "I am already waiting for your response, therefore you cannot close the paginator.",
                ephemeral=True,
            )
            return
        await self.stop_paginator()

    @discord.ui.button(
        emoji="<:next_track:840584439813242951>",
        style=discord.ButtonStyle.grey,
        custom_id="True",
    )
    async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the next page"""
        await self.show_checked_page(self.current_page + 1)

    @discord.ui.button(
        emoji="<:last_track:840584439813373972>",
        style=discord.ButtonStyle.grey,
        custom_id="True",
    )
    async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the last page"""
        await self.show_page(self.source.get_max_pages() - 1)

    @discord.ui.button(
        row=1,
        label="Skip to page...",
        style=discord.ButtonStyle.success,
        custom_id="True",
    )
    async def numbered_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """lets you type a page number to go to"""
        await interaction.response.send_modal(PagePrompterModal(view=self))


class ImageMenu(ViewMenu):
    def __init__(self, delete_after=False, **kwargs):
        super().__init__(
            delete_after=delete_after, **kwargs, is_image_menu=True
        )
        self.fav = {}
        self.info = {}
        self.fav_limit = 4
        self.message = None
        self.current_page: int = 0
        self.clear_items()
        self.add_all_items()

    def add_all_items(self) -> None:
        super().add_all_items()
        if len(self.source.entries) > 1:
            self.add_to_favourite.row = self.delete.row = self.information.row = self.report.row = 2

        self.add_item(self.add_to_favourite)
        self.add_item(self.report)
        self.add_item(self.information)
        self.add_item(self.delete)

    def check_limit(self, limit, counter, user, usersdict):
        if self.source.get_max_pages() <= 1:
            if counter > limit:
                usersdict[user.id] += 1
                raise LimitReached(limit=limit, counter=counter, user=user)
            usersdict[user.id] += 1

    async def edit_fav(self, filename, image_id, user):
        t = await self.bot.waifu_client.fav_toggle(user_id=user.id, image=image_id)
        mes = "**added to**" if t["state"] == "INSERTED" else "**removed from**"
        return f"Alright **{user.name}**, the [image](https://{APIDomainName}/preview/{image_id}), " \
               f"has successfully been {mes} your Gallery.\n" \
               f"You can look at your Gallery [here](https://{APIDomainName}/fav/) " \
               "after logging in with your discord account, or by using the `favourite` command. "

    @discord.ui.button(emoji="⚠", label="Report", style=discord.ButtonStyle.grey, custom_id="True", )
    async def report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReportModal(view=self))

    @discord.ui.button(emoji="❤", style=discord.ButtonStyle.grey)
    async def add_to_favourite(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        self.check_limit(
            self.fav_limit, self.fav.setdefault(user.id, 1), user, self.fav
        )
        filename = str(self.image_info.image_id) + self.image_info.extension
        image_id = self.image_info.image_id
        adv = await self.edit_fav(filename, image_id, user)
        embed = discord.Embed(description=adv, color=discord.Colour.random())
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        emoji="<:dust_bin:825400669867081818>",
        style=discord.ButtonStyle.grey,
        custom_id="True",
    )
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.lock and self.lock.locked():
            return await interaction.response.send_message(
                "I am already waiting for your response...", ephemeral=True
            )
        return await self.stop_paginator()

    @discord.ui.button(
        emoji="<:info:896762508134719520>",
        label="Info",
        row=1,
        style=discord.ButtonStyle.grey,
    )
    async def information(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.check_limit(
            self.fav_limit,
            self.info.setdefault(interaction.user.id, 1),
            interaction.user,
            self.info,
        )
        await interaction.response.defer(ephemeral=True)
        try:
            rq = await self.bot.waifu_client.info(images=[self.image_info.image_id])
            self.image_info = self.source.image_infos[self.current_page] = rq[0]
        except:
            pass
        image_id = self.image_info.image_id
        in_fav = False
        try:
            favs = await self.bot.waifu_client.fav(user_id=interaction.user.id)
            in_fav = any(im.image_id == image_id for im in favs)
        except waifuim.exceptions.APIException as e:
            if e.status != 404:
                raise e
        numberfav = self.image_info.favourites
        sd_part = "If the image doesn't have any source, and you really want it," \
                  "please use **[Saucenao](https://saucenao.com/)**," \
                  f"Join the [support server]({self.bot.server_invite}) and share us the new source."
        description = (
                f"This **[image](https://waifu.im/preview/{image_id})** **is {'not' if not in_fav else 'already'}** in your [gallery](https://waifu.im/fav/)\n\n"
                + sd_part
        )
        embed = discord.Embed(
            colour=discord.Colour.random(),
            title=f"**{numberfav}** ❤",
            description=description,
        )
        for key, value in self.image_info.__dict__.items():
            if key == "tags":
                value = ",".join([f"`{t.name}`" for t in value])
            embed.add_field(
                name=key.replace("_", " ").capitalize(),
                value=value if value is not None else "Sorry this field is empty",
                inline=False,
            )
        return await interaction.followup.send(embed=embed, ephemeral=True)


class FavMenu(ImageMenu):
    @discord.ui.button(
        emoji="❤️", label="Favourite or Remove", style=discord.ButtonStyle.grey
    )
    async def add_to_favourite(
            self, interaction: discord.Interaction, button: discord.ui.Button,
    ):
        await super().add_to_favourite(interaction, button)
        if interaction.user.id == self.main_interaction.user.id:
            self.source.remove(self.current_page)
            if not self.source.entries:
                await self.stop_paginator()
            await self.show_checked_page(self.current_page)
