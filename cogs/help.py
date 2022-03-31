from main import Ayane
from utils import constants, paginators
import math

import discord
from discord.ext import commands

from private.config import LOCAL


class PrivateCategoryOrGroup(Exception):
    def __init__(self, group=False):
        super().__init__(
            f"Sorry this {'group' if group else 'category'} do not contain any public commands "
            "or you do not have the permission to use them here.")


async def setup(bot):
    await bot.add_cog(Help(bot))


class AyaneHelpView(paginators.ViewMenu):
    def __init__(self, help_command, **kwargs):
        self.help_command = help_command
        super().__init__(**kwargs)

    async def reload_items(self):
        self.clear_items()
        await self.add_select_options()
        self.add_all_items()

    async def add_select_options(self):
        options = []
        for cog, cmds in self.help_command.get_bot_mapping().items():
            if cog and cog.__cog_app_commands__:
                options.append(discord.SelectOption(
                    emoji=getattr(cog, 'emoji', None),
                    value=cog.qualified_name,
                    label=f"{cog.qualified_name} [{len(cog.__cog_app_commands__)}]",
                    description=getattr(cog, 'brief', None),
                )
                )
        self.category_selector.options = options

    def add_all_items(self):
        self.add_item(self.category_selector)
        if self.source.is_paginating():
            self.numbered_page.row = 2
            max_pages = self.source.get_max_pages()
            use_last_and_first = max_pages is not None and max_pages >= 2
            if use_last_and_first:
                self.add_item(self.go_to_first_page)
            self.add_item(self.go_to_previous_page)

            self.add_item(self.go_to_next_page)
            if use_last_and_first:
                self.add_item(self.go_to_last_page)
            self.add_item(self.numbered_page)
        self.add_item(self.stop_pages)
        self.add_item(self.go_home)

    @discord.ui.select(placeholder="Select a category", row=0)
    async def category_selector(self, select: discord.ui.Select, interaction: discord.Interaction):
        cog = self.bot.get_cog(select.values[0])
        if cog is None:
            return await interaction.response.send_message("Somehow, that category doesn't exist anymore..."
                                                           "\nIf this error persists, please run the help command "
                                                           "again.",
                                                           ephemeral=True)
        await self.help_command.send_cog_help(cog, view_instance=self)

    @discord.ui.button(emoji='🏡', label='Go Home', row=2)
    async def go_home(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.help_command.send_bot_help(self.help_command.get_bot_mapping(), view_instance=self)

    @discord.ui.button(emoji='🛑', label='Stop', row=2)
    async def stop_pages(self, button: discord.ui.Button, interaction: discord.Interaction):
        await super().stop_pages(button, interaction)

    async def start(self):
        await self.add_select_options()
        await super().start()


class AyaneHelpCommand(commands.HelpCommand):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.verify_checks = False

    async def send_bot_help(self, mapping, view_instance=None):
        embed = discord.Embed(title="Ayane Help", description="A bot for Discord servers\n\nIf you are looking for "
                                                              "the available commands please look for the bot in "
                                                              "your slash command tab, type `/` to display it`",
                              colour=self.context.bot.colour)
        embed.set_thumbnail(url=self.context.bot.user.display_avatar.url)
        embed.add_field(
            name='Get support',
            value=f'To get support, join the [support server]({constants.server_invite})',
            inline=False,
        )
        embed.add_field(
            name='Our API',
            value=f'Here is the API [docs](https://waifu.im/docs), the [Github](https://https://github.com/Waifu-im/) '
                  f'and the API [support server](https://discord.com/invite/Hg8kU9pmx9)',
            inline=True,
        )
        await self.context.send(embed=embed)


class Help(commands.Cog):
    def __init__(self, bot):
        self.brief = 'The bot help command'
        self.bot: Ayane = bot
        self.bot.help_command = AyaneHelpCommand()

    def cog_unload(self) -> None:
        self.bot.help_command = commands.MinimalHelpCommand()
