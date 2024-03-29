import platform
from main import Ayane
from utils import constants

from utils.context import AyaneContext

import discord
from discord.ext import commands
from discord import app_commands


async def setup(bot):
    await bot.add_cog(Info(bot))


class Info(commands.Cog):
    def __init__(self, bot):
        self.emoji = 'ℹ'
        self.brief = 'Information about me!'
        self.bot: Ayane = bot

    @app_commands.command(name='about')
    async def about(self, interaction):
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
            value=f"Owners : {' '.join([f'`{self.bot.get_user(owner)}`' for owner in self.bot.owner_ids])}\n",
            inline=False,
        )
        embed.add_field(
            name="<:stats:846407087491121224> Statistics",
            value=f"\n<:servers:846407428152492122> Servers : `{len(self.bot.guilds)}`"
                  f"\n<:users:846407378047729676> Users : `{len(self.bot.users)}`"
                  f"\n<:text_channel:846407318982885435> Text channels : `{text_channel}`"
                  f"\n<:voice_channel:846407273718743080> Voice channels : `{voice_channel}`"
                  f"\n<:stage_channel:846410090050879529> Stage channels : `{stage_channel}`"
                  f"\n<:bot_commands:846415723798462464> Commands : `{len(self.bot.commands) + len(self.bot.tree.get_commands())}`",
            inline=False,
        )
        embed.add_field(name="OS", value=f"OS : `{platform.system()}`", inline=True)
        embed.add_field(
            name="Versions",
            value=f"<:python:846407588878876683> Python : `{platform.python_version()}`"
                  f"\n<:discordpy:846407533588381756> Discord.py : `{discord.__version__}`",
            inline=False,
        )
        embed.add_field(
            name="Links",
            value=f"[Bot Invite]({self.bot.invite})"
                  f"\n[Support Server]({constants.server_invite})"
                  f"\n[API Documentation](https://waifu.im/docs/)"
                  f"\n[Website]({constants.website})",
            inline=False,
        )
        embed.set_footer(
            text=f"Requested by {interaction.user.name}",
            icon_url=interaction.user.display_avatar.url,
        )
        return await interaction.response.send_message(embed=embed)
