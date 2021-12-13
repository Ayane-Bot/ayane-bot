from discord.ext import commands


def setup(bot):
    bot.add_cog(Info(bot))


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='info', aliases=['about'])
    async def info(self, ctx):
        """
        Displays information about the bot.
        """
        await ctx.send(f'Hello, I am a bot made by `LeoCx1000#9999`, `Buco#1169` and `veryon#1741`!')
