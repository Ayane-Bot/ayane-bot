from main import Ayane
from utils import constants, defaults, paginators
import math

import discord
from discord.ext import commands


from private.config import LOCAL


class PrivateCategoryOrGroup(Exception):
    def __init__(self, group=False):
        super().__init__(
            f"Sorry this {'group' if group else 'category'} do not contain any public commands "
            "or you do not have the permission to use them here.")


def setup(bot):
    bot.add_cog(Help(bot))


class AyaneHelpView(paginators.ViewMenu):
    def __init__(self, help_command, **kwargs):
        self.help_command = help_command
        super().__init__(**kwargs)

    async def reload_items(self):
        self.clear_items()
        await self.add_select_options()
        self.add_all_items()


    async def add_select_options(self):
        options=[]
        for cog, cmds in self.help_command.get_bot_mapping().items():
            cmds=await self.help_command.filter_commands(cmds)
            if cmds and cog:
                options.append(discord.SelectOption(
                    emoji=cog.emoji,
                    value=cog.qualified_name,
                    label=f"{cog.qualified_name} [{len(cmds)}]",
                    description=cog.brief,
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
                self.add_item(self.go_to_first_page)  # type: ignore
            self.add_item(self.go_to_previous_page)  # type: ignore

            self.add_item(self.go_to_next_page)  # type: ignore
            if use_last_and_first:
                self.add_item(self.go_to_last_page)  # type: ignore
            self.add_item(self.numbered_page)  # type: ignore
        self.add_item(self.stop_pages)
        self.add_item(self.go_home)

    @discord.ui.select(placeholder="Select a category",row=0)
    async def category_selector(self, select: discord.ui.Select, interaction: discord.Interaction):
        cog = self.bot.get_cog(select.values[0])
        if cog is None:
            return await interaction.response.send_message("Somehow, that category doesn't exist anymore..."
                                                           "\nThe bot may have restarted while you were interacting "
                                                           "with the help menu. "
                                                           "\nIf this error persists, please run the help command "
                                                           "again.",
                                                           ephemeral=True)
        await self.help_command.send_cog_help(cog, view_instance=self)

    @discord.ui.button(emoji='🏡', label='Go Home',row=2)
    async def go_home(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.help_command.send_bot_help(self.help_command.get_bot_mapping(), view_instance=self)

    @discord.ui.button(emoji='🛑', label='Stop',row=2)
    async def stop_pages(self, button: discord.ui.Button, interaction: discord.Interaction):
        await super().stop_pages(button, interaction)

    async def start(self):
        await self.add_select_options()
        await super().start()


class AyaneHelpCommand(commands.HelpCommand):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.verify_checks=False

    def get_command_signature(self, command):
        return f"{self.context.clean_prefix}{command.qualified_name} {command.signature}"

    async def on_help_command_error(self,ctx, error):
        original_error = getattr(error, 'original', error)
        print("test")
        if isinstance(original_error, PrivateCategoryOrGroup):
            embed = discord.Embed(title="🛑 Private", description=str(original_error))
            await ctx.send(embed=embed)
        elif isinstance(original_error, commands.CommandNotFound):
            embed = discord.Embed(title="❌ Command not found", description=str(original_error))
            await ctx.send(embed=embed)
        else:
            ctx.bypass_first_error_handler=True
            await super().on_help_command_error(ctx, error)


    async def change_view(self, source_items, view_instance=None):
        source_items=source_items if isinstance(source_items,list) else [source_items]
        if view_instance:
            view_instance.source.entries = source_items
            await view_instance.reload_items()
            await view_instance.show_page(0)
            return

        await AyaneHelpView(
            self,
            ctx=self.context,
            source=paginators.BaseSource(source_items, per_page=1),
        ).start()

    def get_bot_mapping(self):
        """Retrieves the bot mapping passed to :meth:`send_bot_help`."""
        bot = self.context.bot
        hidden = ['Jishaku']
        mapping = {cog: cog.get_commands() for cog in bot.cogs.values() if cog.qualified_name not in hidden}
        mapping[None] = [c for c in bot.commands if c.cog is None]
        return mapping

    async def format_cog_and_group(self, cog_or_group):
        group = isinstance(cog_or_group, commands.Group)
        embed_list = []
        items_per_page = 8
        public_commands = await self.filter_commands(cog_or_group.commands if group else cog_or_group.get_commands())

        if not public_commands:
            raise PrivateCategoryOrGroup(group=group)
        pages = math.ceil(len(public_commands) / items_per_page)
        for i in range(pages):
            com_description = ""
            page = i + 1
            start = (page - 1) * items_per_page
            end = start + items_per_page
            for com in public_commands[start:end]:
                com_description += f"`{com.qualified_name}` • {com.short_doc or 'No description'}\n"
            embed = discord.Embed(colour=self.context.bot.colour)
            if group:
                embed.title = f"{cog_or_group.qualified_name.capitalize()}"
                embed.description = f"Use `{self.context.clean_prefix}help <subcommand>`" \
                                    f"for more information about a subcommand.\n\n" \
                                    f"{cog_or_group.help or 'No help provided.'}\n\n{com_description}"
            else:
                embed.title = f"{cog_or_group.emoji} {cog_or_group.qualified_name.capitalize()}"
                embed.description = f"Use `{self.context.clean_prefix}help <command>`" \
                                    f"for more information about a command.\n\n" \
                                    f"{com_description}"

            embed.set_thumbnail(url=self.context.bot.user.display_avatar.url)
            embed.set_footer(
                text=f"Page {page}/{pages}", icon_url=self.context.bot.user.avatar.url
            )
            embed_list.append(embed)
        return embed_list

    async def send_bot_help(self, mapping, view_instance=None):
        embed = discord.Embed(title="Ayane Help", description="A bot for Discord servers", color=self.context.bot.color)
        embed.set_thumbnail(url=self.context.bot.user.display_avatar.url)
        embed.add_field(
            name='Get support',
            value=f'To get support, join the [support server]({constants.server_invite})',
            inline=False,
        )
        await self.change_view(embed, view_instance=view_instance)

    async def send_cog_help(self, cog, view_instance=None):
        await self.change_view(await self.format_cog_and_group(cog),view_instance=view_instance)

    async def send_group_help(self, group, view_instance=None):
        await self.change_view(await self.format_cog_and_group(group),view_instance=view_instance)

    async def send_command_help(self, command):
        channel = self.get_destination()
        command_signatures = self.get_command_signature(command)
        embed = discord.Embed(
            title=command.name,
            description=command.help or "No help provided.",
            colour=self.context.bot.colour,
        )
        embed.add_field(name="Usage", value=f"```{command_signatures}```", inline=False)
        if command.aliases:
            aliases = [f"`{c}`" for c in command.aliases]
            embed.add_field(name="Aliases", value=" , ".join(aliases), inline=False)
        embed.set_footer(
            icon_url=self.context.bot.user.display_avatar.url,
            text="<> Required argument | [] Optional argument",
        )
        await self.context.send(embed=embed)

    def maybe_meant(self, string, group_command=None):
        liste = []
        for command in group_command.commands if group_command else self.context.bot.commands:
            if string.lower() in command.name.lower() and len(string) >= 2:
                liste.append(f"`{command.name}`")
        if not group_command:
            for cog,cmds in self.get_bot_mapping().items():
                if not cmds or not cog:
                    continue
                if string.lower() in cog.qualified_name.lower() and len(string) >= 2:
                    liste.append(f"`{str(cog.qualified_name)}`")
        return liste

    async def command_not_found(self, string):
        liste = self.maybe_meant(string)
        if liste:
            raise commands.CommandNotFound(f"No command or command category called `{string}` found.\n"
                                            f"**Did you mean ?**\n{' , '.join(liste)}")
        else:
            raise commands.CommandNotFound(f"No command or command category called `{string}` found.")

    async def subcommand_not_found(self, command, string):
        liste = self.maybe_meant(string, group_command=command)
        if liste:
            raise commands.CommandNotFound(f"Command `{command.qualified_name}` has no subcommand"
                                            f"called `{string}`."
                                            f"\n**Did you mean ?**\n{' , '.join(liste)}")
        else:
            raise commands.CommandNotFound(f"Command `{command.qualified_name}` has no subcommand"
                                            f"called `{string}`.")


class Help(defaults.AyaneCog, brief='The bot help command'):
    def __init__(self, bot):
        self.bot: Ayane = bot
        self.bot.help_command = AyaneHelpCommand(
            command_attrs=dict(slash_command=not LOCAL, 
                               message_command=LOCAL)
        )

    def cog_unload(self) -> None:
        self.bot.help_command = commands.MinimalHelpCommand()
