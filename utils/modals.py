import discord


class ReportModal(discord.ui.Modal):
    def __init__(self, *, view, **kwargs):
        super().__init__(title="Report", **kwargs)
        self.view = view
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
