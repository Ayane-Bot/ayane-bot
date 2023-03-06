import discord
from discord.ext import commands, tasks


async def setup(bot):
    await bot.add_cog(Guilds(bot))


class Guilds(commands.Cog):
    def __init__(self, bot):
        self.emoji = ''
        self.brief = 'Some personal guild features'
        self.bot = bot
        self.bot.allowed_users = [689058746055262228]
        self.automove_source_channels = [990247228402720808]
        self.automove_target_category = 987106111905734667
        self.automove.start()

    @tasks.loop(seconds=5.0)
    async def automove(self):
        for s in self.automove_source_channels:
            for m in self.bot.get_channel(s).members:
                for channel in [
                    i for i in self.bot.get_channel(self.automove_target_category).channels
                    if isinstance(i, discord.VoiceChannel)
                ]:
                    if len(channel.members) > 0:
                        await m.move_to(channel, reason="Automove")
                        break

    @automove.before_loop
    async def wait_until(self):
        await self.bot.wait_until_ready()
