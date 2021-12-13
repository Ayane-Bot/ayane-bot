import discord

from private.config import LOCAL


class PersistentExceptionView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.bot.is_owner(interaction.user) and LOCAL is False

    @discord.ui.button(emoji='🗑', label='Mark as resolved', custom_id='persistant_exception_view_mark_as_resolved')
    async def resolve(self, _, interaction: discord.Interaction):
        message = interaction.message
        error = '```py\n' + '\n'.join(message.content.split('\n')[7:])
        await message.edit(content=f"{error}```fix\n✅ Marked as fixed by the developers.```", view=None)
