from discord.ext import commands
import datetime


def setup(bot):
    bot.add_cog(Info(bot))


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="info", aliases=["about"])
    async def info(self, ctx):
        """
        Displays information about the bot.
        """
        await ctx.send(
            f"Hello, I am a bot made by `LeoCx1000#9999`, `Buco#1169` and `veryon#1741`!"
        )

    @commands.command(aliases=["info"])
    async def about(self, ctx):
        """Some information about the bot, the bot owners, statistics, OS."""
        text_channel = 0
        voice_channel = 0
        stage_channel = 0
        for channel in self.bot.get_all_channels():
            if isinstance(channel, discord.TextChannel):
                text_channel += 1
            elif isinstance(channel, discord.VoiceChannel):
                voice_channel += 1
            elif isinstance(channel, discord.StageChannel):
                stage_channel += 1
        bot_users = len(self.bot.users)
        command_count = len(self.bot.commands)
        guilds = len(self.bot.guilds)
        owners_string = " ".join([f"`{own}`" for own in self.bot.owner_ids])
        embed = discord.Embed(
            title="Information about the bot",
            color=self.bot.mycolor,
        )
        embed.set_thumbnail(url=owner.avatar.url)
        embed.add_field(
            name="<:bot_owner:846407210493804575> Owners",
            value=f"Owners : {owners_string}\n",
            inline=False,
        )
        embed.add_field(
            name="<:stats:846407087491121224> Statistics",
            value=f"""
<:servers:846407428152492122> Servers : `{guilds}`
<:users:846407378047729676> Users : `{bot_users}`
<:voice_channel:846407273718743080> Voice channels : `{voice_channel}`
<:text_channel:846407318982885435> Text channels : `{text_channel}`
<:stage_channel:846410090050879529> Stage channels : `{stage_channel}`
<:bot_commands:846415723798462464> Commands : `{command_count}`""",
            inline=False,
        )
        embed.add_field(name="OS", value=f"OS : `{platform.system()}`", inline=True)
        embed.add_field(
            name="Versions",
            value=f"<:python:846407588878876683> Python : `{platform.python_version()}`\n<:discordpy:846407533588381756> Discord.py : `{discord.__version__}`",
            inline=False,
        )
        embed.add_field(
            name="Links",
            value=f"""
[Bot Invite]({self.bot.invite})
[Support Server]({self.bot.server_invite})
[API Documentation](https://waifu.im/docs/)
[Website]({self.bot.website})""",
            inline=False,
        )
        embed.set_footer(
            text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url
        )
        embed.timestamp = datetime.datetime.utcnow()
        message = await ctx.send(embed=embed)
