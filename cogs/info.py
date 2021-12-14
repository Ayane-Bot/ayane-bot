import discord
from discord.ext import commands

import platform
import datetime


def setup(bot):
    bot.add_cog(Info(bot))


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=['info'])
    async def about(self, ctx):
        """Some information about the bot like the bot owners, statistics etc."""
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
        
        embed = discord.Embed(
            title="Information about the bot",
            color=self.bot.colour,
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(
            name="<:bot_owner:846407210493804575> Owners",
            value=f"Owners : {' '.join([f'`{owner}`' for owner in self.bot.owner_ids])}\n",
            inline=False,
        )
        embed.add_field(
            name="<:stats:846407087491121224> Statistics",
            value=f"""
<:servers:846407428152492122> Servers : `{len(self.bot.guilds):,}`
<:users:846407378047729676> Users : `{len(self.bot.users):,}`
<:text_channel:846407318982885435> Text channels : `{text_channel:,}`
<:voice_channel:846407273718743080> Voice channels : `{voice_channel:,}`
<:stage_channel:846410090050879529> Stage channels : `{stage_channel:,}`
<:bot_commands:846415723798462464> Commands : `{len(self.bot.commands):,}`""",
            inline=False,
        )
        embed.add_field(name="OS", value=f"OS : `{platform.system()}`", inline=True)
        embed.add_field(
            name="Versions",
            value=f"""
<:python:846407588878876683> Python : `{platform.python_version()}`
<:discordpy:846407533588381756> Discord.py : `{discord.__version__}`""",
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
            text=f"Requested by {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )
        
        await ctx.send(embed=embed)
