import typing

import discord
import jishaku
from discord.ext import commands

import platform

from main import Ayane
from utils import constants
from utils.defaults import AyaneCog, ayane_command
from utils.context import AyaneContext


def setup(bot):
    bot.add_cog(Info(bot))


class AyaneHelpView(discord.ui.View):
    def __init__(self, mapping: typing.Dict[AyaneCog, typing.List[commands.Command]], /, *, bot: Ayane):
        super().__init__(timeout=120)
        self.message: discord.Message = None
        self.mapping = mapping
        self.bot = bot
        self.main_page: discord.Embed = None

    def build_cog_page(self, cog: AyaneCog, /):
        cog_commands = self.mapping[cog]
        if not cog_commands:
            return discord.Embed(title='Something happened...', description='This cog has no commands...', color=self.bot.color)
        embed = discord.Embed(title=f"{cog.emoji} {cog.qualified_name}", description=cog.brief, color=self.bot.color)
        embed.set_thumbnail(url=cog.icon or discord.Embed.Empty)
        for cmd in cog_commands:
            if len(embed.fields) >= 25:
                break
            embed.add_field(name=f"`{cmd.name}{f' {cmd.signature}`' if cmd.signature else '`'}", value=cmd.brief or cmd.help or 'No help given...', inline=False)
        return embed

    def build_main_page(self):
        if self.main_page:
            return self.main_page
        embed = discord.Embed(title="Ayane Help", description="A bot for Discord servers", color=self.bot.color)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name='Get support', value=f'To get support, join the [support server]({constants.server_invite})', inline=False)
        self.main_page = embed
        return embed

    @discord.ui.select(placeholder="Select a category")
    async def category_selector(self, select: discord.ui.Select, interaction: discord.Interaction):
        response: discord.InteractionResponse = interaction.response
        cog = self.bot.get_cog(select.values[0])
        if cog is None:
            return await response.send_message("Somehow, that category doesn't exist anymore..."
                                               "\nThe bot may have restarted while you were interacting with the help menu."
                                               "\nIf this error persists, please run the help command again.", ephemeral=True)
        embed = self.build_cog_page(cog)
        await response.edit_message(embed=embed)

    @discord.ui.button(emoji='🏡', label='Go Home')
    async def go_home(self, _, interaction: discord.Interaction):
        response: discord.InteractionResponse = interaction.response
        embed = self.build_main_page()
        await response.edit_message(embed=embed)

    @discord.ui.button(emoji='🛑', label='Stop')
    async def _stop(self, _, interaction: discord.Interaction):
        await interaction.message.delete()
        self.stop()

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)

    async def start(self, ctx: AyaneContext):
        options = []
        for cog, cmds in self.mapping.items():
            if not cmds:
                continue
            options.append(discord.SelectOption(value=cog.qualified_name, label=f"{cog.qualified_name} [{len(cmds)}]", description=cog.brief))
        self.category_selector.options = options

        embed = self.build_main_page()
        self.message = await ctx.send(embed=embed, view=self)


class AyaneHelpCommand(commands.HelpCommand):

    def get_bot_mapping(self):
        """Retrieves the bot mapping passed to :meth:`send_bot_help`."""
        bot = self.context.bot
        hidden = ['Jishaku']
        mapping = {cog: cog.get_commands() for cog in bot.cogs.values() if cog.qualified_name not in hidden}
        return mapping

    async def send_bot_help(self, mapping):
        view = AyaneHelpView(mapping, bot=self.context.bot)
        await view.start(self.context)


class Info(AyaneCog, emoji='ℹ', brief='Information about me!'):
    def __init__(self, bot):
        self.bot: Ayane = bot
        help_command = AyaneHelpCommand()
        help_command.cog = self
        self.bot.help_command = help_command

    def cog_unload(self) -> None:
        self.bot.help_command = commands.MinimalHelpCommand()

    @ayane_command(aliases=['info'])
    async def about(self, ctx: AyaneContext):
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
            value=f"\n<:servers:846407428152492122> Servers : `{len(self.bot.guilds):,}`"
                  f"\n<:users:846407378047729676> Users : `{len(self.bot.users):,}`"
                  f"\n<:text_channel:846407318982885435> Text channels : `{text_channel:,}`"
                  f"\n<:voice_channel:846407273718743080> Voice channels : `{voice_channel:,}`"
                  f"\n<:stage_channel:846410090050879529> Stage channels : `{stage_channel:,}`"
                  f"\n<:bot_commands:846415723798462464> Commands : `{len(self.bot.commands):,}`",
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
            text=f"Requested by {ctx.author.name}",
            icon_url=ctx.author.display_avatar.url,
        )
        await ctx.send(embed=embed)
