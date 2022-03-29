import discord


class BaseModal(discord.ui.Modal):
    def __init__(self, *, view, title="No Title", **kwargs):
        super().__init__(title=title, **kwargs)
        self.view = view

    async def on_error(self, error: Exception, interaction) -> None:
        await self.view.on_error(error, None, interaction)


class ReportModal(BaseModal):
    def __init__(self, **kwargs):
        super().__init__(title="Report", **kwargs)
        self.reason = discord.ui.TextInput(
            "What is the problem with this picture ?",
            min_length=5,
            max_length=200,
            placeholder="Contain a loli / Tags are incorrect / Here is the new source : https://example.com/ "
        )

    async def on_submit(self, interaction) -> None:
        await self.view.bot.waifu_client.report(
            self.view.image_info.file,
            user_id=interaction.user.id,
            description=self.reason.value.strip(" "),
        )
        await interaction.followup.send(
            "Your report has successfully been sent. Thank you for your help!",
            ephemeral=True,
        )
        self.view.source.remove(self.view.current_page)
        if not self.view.source.entries:
            await self.view.stop_paginator()
        await self.view.show_checked_page(self.view.current_page)


class PagePrompterModal(BaseModal):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_page = self.view.source.get_max_page() - 1
        self.title = f"Select a page number between 1 and {self.max_page}"
        self.page = discord.ui.TextInput(
            "Page",
            min_length=1,
            max_length=len(str(self.max_page)),
        )

    async def on_submit(self, interaction) -> None:
        try:
            page = int(self.page.value)
        except ValueError:
            return await interaction.response.send_message(f"{self.page.value} is not a valid page")
        await self.view.show_checked_page(page)
