import asyncio

import discord
import humanize.time
import waifuim
from discord.ext import commands, menus

import os

from utils.constants import APIDomainName
from utils.exceptions import NotAuthorized, LimitReached, UserBlacklisted
from utils.lock import UserLock

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
                url=f"https://{APIDomainName}/preview/?image=" + im["file"] + im["extension"],
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
            timeout=840,
            **kwargs,
    ):
        super().__init__(timeout=timeout, **kwargs)
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
        self.no_author_check = []

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
            await self.ctx.message.add_reaction("<:verified_purple:840584369294671902>")
        except discord.DiscordException:
            pass

    async def interaction_check(self, item, interaction):
        reason = await self.bot.is_blacklisted(interaction.user)
        if reason:
            raise UserBlacklisted(interaction.user, reason=reason[0])
        if (
                item not in self.no_author_check
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

        if self.main_interaction:
            if self.main_interaction.response.is_done():
                return await self.main_interaction.edit_original_message(
                    *args, **kwargs, view=self
                )
            else:
                await self.main_interaction.response.send_message(
                    *args,
                    **kwargs,
                    ephemeral=self.ephemeral,
                    view=self
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
        send_error_message = self.bot.get_cog("Events").send_interaction_error_message
        send_unexpected_error = self.bot.get_cog("Events").send_unexpected_error
        if isinstance(error, NotAuthorized):
            return await send_error_message(interaction, str(error), ephemeral=True)
        elif isinstance(error, LimitReached):
            await send_error_message(
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
        elif isinstance(error, discord.ext.commands.NotOwner):
            embed = discord.Embed(
                title="🛑 Owner-only",
                colour=self.bot.colour,
                description=f"Sorry **{interaction.user}**, but this command is an owner-only command and "
                            f"you arent one of my loved developers <:ty:833356132075700254>."
            )
            await send_error_message(
                interaction, embed=embed, ephemeral=True
            )
        elif isinstance(error, UserBlacklisted):
            embed = discord.Embed(title="🛑 Forbidden", colour=self.bot.colour, description=str(error))
            await send_error_message(
                interaction, embed=embed, ephemeral=True
            )
        else:
            await send_unexpected_error(self.ctx, error, user=interaction.user, interaction=interaction, ephemeral=True)


class ViewMenuLauncher(BaseView):
    def __init__(self, viewmenu=None, **kwargs):
        self.result = False
        self.viewmenu = viewmenu
        self.ctx = self.viewmenu.ctx
        super().__init__(ctx=self.ctx, timeout=30, **kwargs)

    async def disable(self):
        self.confirm.disabled = True
        self.remove_item(self.delete)
        await self.message.edit(
            view=self,
            content="This message will disappear once you **properly** close the paginator,"
                    "use the stop (square or dustbin) button to do so.",
        )

    @discord.ui.button(emoji="✅", style=discord.ButtonStyle.grey)
    async def confirm(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        """go to the first page"""
        self.viewmenu.main_interaction = interaction
        self.viewmenu.ephemeral = True
        self.result = True
        await self.viewmenu.start()
        await self.disable()
        await self.viewmenu.wait()
        await self.stop_paginator()

    @discord.ui.button(emoji="<:dust_bin:825400669867081818>", style=discord.ButtonStyle.grey)
    async def delete(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.stop_paginator()

    async def on_timeout(self):
        if not self.result:
            await self.stop_paginator()

    async def start(self):
        if self.viewmenu.asked_for_ephemeral and not self.viewmenu.main_interaction:
            self.lock = UserLock(
                self.ctx.author,
                error_message=f"I am already waiting for you to choose one of the"
                              f"2 buttons for the `{self.ctx.command.name}` command.",
            )
            async with self.lock(self.bot):
                self.message = await self.ctx.send(
                    f"Click ✅ to get your ephemeral message ! (you have {humanize.time.precisedelta(int(self.timeout))})\n{f'⚠ Be careful this command may contain age-restricted content. <:YuriLaugh:846478037435809852>' if hasattr(self.ctx.command, 'nsfw') or hasattr(self.ctx, 'nsfw') else ''}",
                    view=self,
                )
        else:
            await self.viewmenu.start()


class ViewMenu(BaseView):
    def __init__(
            self,
            source=None,
            imagemenu=None,
            **kwargs,
    ):
        super().__init__(**kwargs)
        self.source = source
        if not self.source:
            raise TypeError("source is a required argument")
        self.imagemenu = imagemenu
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
            if not self.imagemenu:
                self.add_item(self.stop_pages)
            self.add_item(self.numbered_page)

    async def _get_kwargs_from_page(self, page: int):
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if self.imagemenu:
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
            self.message = await self.message.edit(**kwargs, view=self)

    async def show_checked_page(
            self, page_number: int
    ):
        max_page = self.source.get_max_pages()
        try:
            if max_page is None:
                # If it doesn't give maximum pages, it cannot be checked
                await self.show_page(page_number)
            elif page_number >= max_page:
                await self.show_page(max_page - 1)
            elif page_number < 0:
                await self.show_page(0)
            elif max_page > page_number >= 0:
                await self.show_page(page_number)
        except IndexError:
            # An error happened that can be handled, so ignore it.
            pass

    async def start(self):
        if (
                self.check_embeds
                and not self.ctx.channel.permissions_for(self.ctx.me).embed_links
        ):
            await self.ctx.send(
                "Bot does not have embed links permission in this channel."
            )
            return
        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        self.update_items(0)
        self.message = await self.send_view(**kwargs)

    @discord.ui.button(
        emoji="<:first_track:840584439830544434>",
        style=discord.ButtonStyle.grey,
    )
    async def go_to_first_page(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        """go to the first page"""
        await self.show_page(0)

    @discord.ui.button(
        emoji="<:before_track:840584439817699348>",
        style=discord.ButtonStyle.grey,
    )
    async def go_to_previous_page(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        """go to the previous page"""
        await self.show_checked_page(self.current_page - 1)

    @discord.ui.button(
        row=1,
        emoji="<:stop_track:840584439825825802>",
        style=discord.ButtonStyle.grey,
    )
    async def stop_pages(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
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
    )
    async def go_to_next_page(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        """go to the next page"""
        await self.show_checked_page(self.current_page + 1)

    @discord.ui.button(
        emoji="<:last_track:840584439813373972>",
        style=discord.ButtonStyle.grey,
    )
    async def go_to_last_page(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(self.source.get_max_pages() - 1)

    @discord.ui.button(
        row=1,
        label="Skip to page...",
        style=discord.ButtonStyle.success,
    )
    async def numbered_page(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        """lets you type a page number to go to"""
        if self.lock and self.lock.locked():
            await interaction.response.send_message(
                "I am already waiting for your response...", ephemeral=True
            )
            return

        if self.message is None:
            return
        self.lock = UserLock(interaction.user)
        async with self.lock(self.bot):
            channel = self.message.channel
            author_id = interaction.user and interaction.user.id
            await interaction.response.send_message(
                "Please give me the page number you want to go or cancel with `cancel`.",
                ephemeral=True,
            )

            def message_check(m):
                return m.author.id == author_id and channel.id == m.channel.id

            while True:
                try:
                    msg = await self.bot.wait_for(
                        "message", check=message_check, timeout=30.0
                    )
                except asyncio.TimeoutError:
                    return await interaction.followup.send(
                        "Operation has been canceled", ephemeral=True
                    )
                else:
                    if msg.content.lower() == "cancel":
                        return await interaction.followup.send(
                            "The operation has been canceled", ephemeral=True
                        )
                    if not msg.content.isdigit():
                        continue
                    page = int(msg.content)
                    maxpage = self.source.get_max_pages()
                    if page > maxpage:
                        page = maxpage

                    if page < 1:
                        page = 1

                    return await self.show_checked_page(page - 1)


class ImageMenu(ViewMenu):
    def __init__(self, delete_after=False, **kwargs):
        super().__init__(
            delete_after=delete_after, **kwargs, imagemenu=True
        )
        self.fav = {}
        self.info = {}
        self.fav_limit = 4
        self.message = None
        self.current_page: int = 0
        self.clear_items()
        self.add_all_items()
        self.no_author_check = [self.add_to_favourite, self.informations]

    def add_all_items(self) -> None:
        super().add_all_items()
        if len(self.source.entries) > 1:
            self.add_to_favourite.row = self.delete.row = self.informations.row = self.report.row = 2

        self.add_item(self.add_to_favourite)
        self.add_item(self.report)
        self.add_item(self.informations)
        self.add_item(self.delete)

    def check_limit(self, limit, counter, user, usersdict):
        if self.source.get_max_pages() <= 1:
            if counter > limit:
                usersdict[user.id] += 1
                raise LimitReached(limit=limit, counter=counter, user=user)
            usersdict[user.id] += 1

    async def editfav(self, image_name, image, user):
        t = await self.bot.waifuclient.fav(user_id=user.id, toggle=[image_name])
        inserted = image_name in t.get("inserted") and image_name not in t.get(
            "deleted"
        )
        deleted = image_name in t.get("deleted") and image_name not in t.get("inserted")
        if inserted:
            mes = "**added** to"
        elif deleted:
            mes = "**removed** from"
        else:
            raise RuntimeError("The image is not in either inserted or deleted")
        return f"Alright **{user.name}**, the [image](https://{APIDomainName}/preview/?image={image}), " \
               f"has successfully been {mes} your Gallery.\n" \
               f"You can look at your Gallery [here](https://{APIDomainName}/fav/) " \
               "after logging in with your discord account, or by using the `favourite` command. "

    @discord.ui.button(emoji="⚠", label="Report", style=discord.ButtonStyle.grey)
    async def report(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        if self.lock and self.lock.locked():
            return await interaction.response.send_message("I am already waiting for your response...", ephemeral=True)
        if interaction.user.id in {*self.bot.waifu_reason_exempted_users, self.bot.owner_id, *self.bot.owner_ids}:
            desc = "Owner report." if interaction.user.id in self.bot.owner_ids else "No reason required for this user."
            await self.bot.waifuclient.report(self.image_info["file"], user_id=interaction.user.id, description=desc)
            await interaction.response.send_message(
                "Your report has successfully been sent. Thank you for your help!",
                ephemeral=True,
            )
        else:
            timeout_verif = 45
            embed = discord.Embed(
                title="Can you describe me the problem with this image ?",
                colour=discord.Colour.random(),
                description=f"**Please read carefully !**\nHi **{interaction.user.name}**, you "
                            f"have **{humanize.time.precisedelta(timeout_verif)}** to send me a message "
                            "containing your description of the problem.\nPlease report the image if it " 
                            "__contains lolis__ or if it is __not related to the command title__.\n"
                            "After this time the operation will be aborted.\n"
                            "If you want to get back on your decision send `cancel`.\n\n"
                            "⚠ You will need to **mention me** for discord to let me access the message content.",
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            self.lock = UserLock(interaction.user)
            async with self.lock(self.bot):
                while True:
                    def check_u(msg):
                        return interaction.user.id == msg.author.id and msg.channel.id == self.ctx.channel.id
                    try:
                        message_user = await self.bot.wait_for("message", timeout=float(timeout_verif), check=check_u)
                    except asyncio.TimeoutError:
                        return await interaction.followup.send(
                            "You took too much time to respond, the operation has been canceled.",
                            ephemeral=True,
                        )
                    else:
                        print("tatatatatata")
                        if (await self.bot.get_context(message_user)).valid:
                            print("test")
                            continue
                        if "cancel" == message_user.content.lower():
                            return await interaction.followup.send("The operation has been canceled.", ephemeral=True)
                        if len(message_user.content) > 200:
                            await interaction.followup.send(
                                "Your reason is to big, please send a shorter description.",
                                ephemeral=True
                            )
                            continue
                        report_desc = message_user.content.replace(f'<@{self.bot.user.id}>','').replace(
                            f'<@!{self.bot.user.id}>',
                            ''
                        )
                        await self.bot.waifuclient.report(
                            self.image_info["file"],
                            user_id=interaction.user.id,
                            description=report_desc.strip(" "),
                        )
                        await interaction.followup.send(
                            "Your report has successfully been sent. Thank you for your help!",
                            ephemeral=True,
                        )
                        break
        self.source.remove(self.current_page)
        if not self.source.entries:
            await self.stop_paginator()
        return await self.show_checked_page(self.current_page)

    @discord.ui.button(emoji="❤", style=discord.ButtonStyle.grey)
    async def add_to_favourite(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        user = interaction.user
        self.check_limit(
            self.fav_limit, self.fav.setdefault(user.id, 1), user, self.fav
        )
        image = self.image_info["file"] + self.image_info["extension"]
        image_name = self.image_info["file"]
        adv = await self.editfav(image_name, image, user)
        embed = discord.Embed(description=adv, color=discord.Colour.random())
        return await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        emoji="<:dust_bin:825400669867081818>",
        style=discord.ButtonStyle.grey,
    )
    async def delete(self, button: discord.ui.Button, interaction: discord.Interaction):
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
    async def informations(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        self.check_limit(
            self.fav_limit,
            self.info.setdefault(interaction.user.id, 1),
            interaction.user,
            self.info,
        )
        await interaction.response.defer(ephemeral=True)
        try:
            rq = await self.bot.waifuclient.info(images=[self.image_info["file"]])
            self.image_info = self.source.imageinfos[self.current_page] = rq["images"][
                0
            ]
        except:
            pass

        image_name = self.image_info["file"]
        image = image_name + self.image_info["extension"]
        in_fav = False
        try:
            favs = await self.bot.waifuclient.fav(user_id=interaction.user.id)
            for im in favs["images"]:
                if image_name == im["file"]:
                    in_fav = True
                    break

        except waifuim.exceptions.APIException as e:
            if e.status != 404:
                raise e
        numberfav = self.image_info["like"]
        sd_part = "If the image doesn't have any source, and you really want it," \
                  "please use **[Saucenao](https://saucenao.com/)**," \
                  f"Join the [support server]({self.bot.server_invite}) and share us the new source."
        description = (
                f"This **[image](https://waifu.im/preview/?image={image})** **is {'not' if not in_fav else 'already'}** in your [gallery](https://waifu.im/fav/)\n\n"
                + sd_part
        )
        embed = discord.Embed(
            colour=discord.Colour.random(),
            title=f"**{numberfav}** ❤",
            description=description,
        )
        for key, value in self.image_info.items():
            if key == "tags":
                value = ",".join([f"`{t['name']}`" for t in value])
            embed.add_field(
                name=key.replace("_", " ").capitalize(),
                value=value if value is not None else "Sorry this field is empty",
                inline=False,
            )
        return await interaction.followup.send(embed=embed, ephemeral=True)


class FavMenu(ImageMenu):

    @discord.ui.button(
        emoji="❤️", label="Like or Remove", style=discord.ButtonStyle.grey
    )
    async def add_to_favourite(
            self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await super().add_to_favourite(button, interaction)
        if interaction.user.id == self.ctx.author.id:
            self.source.remove(self.current_page)
            if not self.source.entries:
                await self.stop_paginator()
            await self.show_checked_page(self.current_page)
