import contextlib
import inspect
import io
import logging
import math
import traceback
import typing

import discord
import humanize as humanize
from discord.ext import commands

from utils import constants, defaults, exceptions
from utils.helpers import PersistentExceptionView
from main import Ayane
from private.config import LOCAL, LOCAL_USER, DEFAULT_PREFIXES

string_map = {
    discord.Member: "member",
    discord.User: "user",
    discord.Message: "message",
    discord.PartialMessage: "message",
    discord.TextChannel: "channel",
    discord.VoiceChannel: "voice channel",
    discord.StageChannel: "stage channel",
    discord.StoreChannel: "store channel",
    discord.CategoryChannel: "category channel",
    discord.Invite: "invite",
    discord.Guild: "server",
    discord.Role: "role",
    discord.Game: "game",
    discord.Colour: "colour",
    discord.Emoji: "emoji",
    discord.PartialEmoji: "emoji",
    int: "whole number",
    float: "number",
    str: "string",
    bool: "boolean",
}


def join_literals(annotation: inspect.Parameter.annotation, return_list: bool = False):
    if typing.get_origin(annotation) is typing.Literal:
        arguments = annotation.__args__
        if return_list is False:
            return '[' + '|'.join(arguments) + ']'
        else:
            return list(arguments)
    return None


def convert_union_annotations(param: inspect.Parameter):
    annotations = param.annotation
    args = typing.get_args(annotations)
    maybe_strings = [string_map.get(a, a) for a in args]
    for a in maybe_strings:
        if not isinstance(a, str):
            if argument := join_literals(a):
                maybe_strings.remove(a)
                maybe_strings.append(f"[{argument}]")
            else:
                maybe_strings.remove(a)
                maybe_strings.append('[unknown]')
    return ", ".join(maybe_strings[:-2] + [" or ".join(maybe_strings[-2:])])


def conv_n(tuple_acc):
    """A really bad code, but i'm lazy to fix"""
    returning = ""
    op_list_v = []
    op_list_n = list(tuple_acc)
    for i in range(len(op_list_n)):
        op_list_v.append(op_list_n[i].__name__.replace("Converter", ""))
    for i in range(len(op_list_v)):
        if i + 3 <= len(op_list_v):
            returning += f"{op_list_v[i].lower()}, "
        elif i + 2 <= len(op_list_v):
            returning += f"{op_list_v[i].lower()} or "
        else:
            returning += f"{op_list_v[i].lower()}"
    return returning


def setup(bot):
    bot.add_cog(Events(bot))


class Events(defaults.AyaneCog, emoji='⚙', brief='Ayane Internal Stuff'):
    def __init__(self, bot):
        self.bot: Ayane = bot

    @staticmethod
    async def send_interaction_error_message(interaction, *args, **kwargs):
        if interaction.response.is_done():
            await interaction.followup.send(*args, **kwargs)

        else:
            await interaction.response.send_message(*args, **kwargs)

    @staticmethod
    async def send_unexpected_error(ctx, error, user=None, interaction=None, **kwargs):
        with contextlib.suppress(discord.HTTPException):
            _message = f"Sorry, an error has occured, it has been reported to my developers. To be inform of the " \
                       f"bot issues and updates join the [support server]({constants.server_invite}) !"
            embed = discord.Embed(title="❌ Error", colour=ctx.bot.colour, description=_message)
            embed.add_field(name="Traceback :", value=f"```py\n{type(error).__name__} : {error}```")

            if interaction:
                await ctx.bot.get_cog("Events").send_interaction_error_message(interaction, embed=embed, **kwargs)

            else:
                await ctx.send(embed=embed, **kwargs)

        error_channel = ctx.bot.get_channel(920086735755575327)
        traceback_string = "".join(traceback.format_exception(etype=None, value=error, tb=error.__traceback__))

        if ctx.guild:
            command_data = (
                f"by: {user.name if user else ctx.author.name} ({user.id if user else ctx.author.id})"
                f"\ncommand: {ctx.message.content[0:1700]}"
                f"\nguild_id: {ctx.guild.id} - channel_id: {ctx.channel.id}"
                f"\nowner: {ctx.guild.owner.name} ({ctx.guild.owner.id})"
                f"\nbot admin: {'✅' if ctx.me.guild_permissions.administrator else '❌'} "
                f"- role pos: {ctx.me.top_role.position}"
            )
        else:
            command_data = (
                f"command: {ctx.message.content[0:1700]}"
                f"\nCommand executed in DMs"
            )

        if LOCAL:
            local_data = f'\nError occured in local mode with user of "from {LOCAL_USER}"'
        else:
            local_data = ''

        to_send = (
            f"```yaml\n{command_data}``````py"
            f"\nCommand {ctx.command} raised the following error:{local_data}"
            f"\n{traceback_string}\n```"
        )

        try:
            if len(to_send) < 2000:
                await error_channel.send(to_send, view=PersistentExceptionView(ctx.bot))
            else:
                file = discord.File(
                    io.StringIO(traceback_string), filename="traceback.py"
                )
                await error_channel.send(
                    f"```yaml\n{command_data}``````py Command {ctx.command} raised the following error:{local_data}\n```",
                    file=file,
                    view=PersistentExceptionView(ctx.bot),
                )
        finally:
            for line in traceback_string.split("\n"):
                logging.info(line)

    @commands.Cog.listener("on_command_error")
    async def error_log(self, ctx, error):
        """Handles command exceptions and logs unhandled ones to the support guild."""
        if hasattr(ctx.command, 'on_error') and not hasattr(ctx, 'bypass_first_error_handler'):
            return

        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        ignored = [
                      commands.CommandNotFound,
                  ] + ([commands.CheckFailure] if LOCAL else [])
        if isinstance(error, tuple(ignored)):
            return
        try:
            await ctx.message.add_reaction("<:verif_red_check:845634265333104682>")
        except discord.DiscordException:
            pass

        # TODO: Leo: Work on better UserInputError messages.
        if isinstance(error, commands.UserInputError):
            embed = discord.Embed(title='An incorrect argument was passed.')

            if isinstance(error, exceptions.UserLocked):
                embed.title = '❌ Multiples Commands Running'
                embed.description = f"Hey **{ctx.author}**,one thing after an other. " + str(error)

            elif isinstance(error, commands.BadUnionArgument):
                embed.description = f"You did not provide a valid {conv_n(error.converters)}, please go check `{ctx.clean_prefix}help {ctx.command.name}`."
                embed.title = "❌ Bad argument"

            elif isinstance(error, commands.BadLiteralArgument):
                embed.title = "❌ Bad argument"
                literals = join_literals(error.param.annotation, return_list=True)
                literals = '"' + '", "'.join(literals[:-2] + ['" or "'.join(literals[-2:])]) + '"'
                embed.description = f"The `{error.param.name}` argument must be one of the following: {literals}"

            elif isinstance(error, commands.ArgumentParsingError):
                if isinstance(error, commands.UnexpectedQuoteError):
                    embed.title = "❌ Invalid Quote Mark"
                    embed.description = f'Unexpected quote mark, {error.quote!r}, in non-quoted string'

                elif isinstance(error, commands.ExpectedClosingQuoteError):
                    embed.title = "❌ Missing Closing Quote"
                    embed.description = f"Expected closing {error.close_quote}."

                elif isinstance(error, commands.InvalidEndOfQuotedStringError):
                    embed.title = "❌ Invalid Character after Quote"
                    embed.description = f'Expected a space after closing quotation but received {error.char!r}'
                else:
                    embed.title = "❌ Sorry, Something went wrong while reading your message..."

            elif isinstance(error, commands.BadArgument):

                if isinstance(error, commands.UserNotFound):
                    embed.description = f"You did not provide a valid user, please go check `{ctx.clean_prefix}help {ctx.command.name}`."
                    embed.title = "❌ User not found"

                elif isinstance(error, commands.MemberNotFound):
                    embed.description = f"You did not provide a valid member, Please go check `{ctx.clean_prefix}help {ctx.command.name}`."
                    embed.title = "❌ Member not found"

                elif isinstance(error, commands.RoleNotFound):
                    embed.description = f"You did not provide a valid role, Please go check `{ctx.clean_prefix}help {ctx.command.name}`."
                    embed.title = "❌ Role not found"

                else:
                    embed.description = f"You provided at least one wrong argument. Please go check `{ctx.clean_prefix}help {ctx.command}`"
                    embed.title = "❌ Bad argument"

            else:
                embed.description = f"You made an error in your commmand. Please go check `{ctx.clean_prefix}help {ctx.command}`"
                embed.title = "❌ Input error"

            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.BotMissingPermissions):
            missing = [(e.replace('_', ' ').replace('guild', 'server')).title() for e in error.missing_permissions]
            perms_formatted = "**, **".join(missing[:-2] + ["** and **".join(missing[-2:])])
            _message = f"I need the **{perms_formatted}** permission(s) to run this command."
            embed = discord.Embed(title="❌ Bot missing permissions", description=_message)
            await ctx.send(embed=embed)

        elif isinstance(error, commands.DisabledCommand):
            if ctx.command.enabled:
                _message = str(error)
            else:
                _message = f"`{ctx.command.name}` command has been temporally disabled, it is probably under maintenance. For more information join the [support server]({constants.server_invite})!"
            embed = discord.Embed(title="🛑 Command disabled", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.MaxConcurrencyReached):
            _message = f"This command can only be used **{error.number}** time simultaneously, please retry later."
            embed = discord.Embed(title="🛑 Maximum concurrency reached", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.CommandOnCooldown):
            _message = f"This command is on cooldown, please retry in {humanize.time.precisedelta(math.ceil(error.retry_after))}."
            embed = discord.Embed(title="🛑 Command on cooldown", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.MissingPermissions):
            missing = [(e.replace('_', ' ').replace('guild', 'server')).title() for e in error.missing_permissions]
            perms_formatted = "**, **".join(missing[:-2] + ["** and **".join(missing[-2:])])
            _message = f"You need the **{perms_formatted}** permission(s) to use this command."
            embed = discord.Embed(title="🛑 Missing permissions", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.MissingRole):
            missing = error.missing_role
            _message = f"You need the **{missing}** role to use this command."
            embed = discord.Embed(title="🛑 Missing role", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, discord.Forbidden):
            _message = "I dont have the permissions to run this command."
            embed = discord.Embed(title="❌ Permission error", description=_message)
            await ctx.send(embed=embed)

        elif isinstance(error, commands.NSFWChannelRequired):
            _message = "Sorry, I cannot display **NSFW** content in this channel."
            embed = discord.Embed(title="🛑 NSFW channel required", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.NoPrivateMessage):
            return

        elif isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                title="🛑 Owner-only",
                description=f"Sorry **{ctx.author}**, but this commmand is an owner-only command and "
                            f"you arent one of my loved developers <:ty:833356132075700254>."
            )
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, exceptions.UserBlacklisted):
            embed = discord.Embed(title="🛑 Blacklisted", description=str(error))
            await ctx.send(embed=embed)

        elif isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                title="🛑 Forbidden",
                description="You do not have the permissions to use this command.",
            )
            await ctx.send(embed=embed, delete_after=15)

        else:
            await self.send_unexpected_error(ctx, error)

    @commands.Cog.listener("on_command")
    async def basic_command_logger(self, ctx):
        await self.bot.db.execute(
            "INSERT INTO commands (guild_id, user_id, command, timestamp) VALUES ($1, $2, $3, $4)",
            getattr(ctx.guild, "id", None),
            ctx.author.id,
            ctx.command.qualified_name,
            ctx.message.created_at,
        )

    @commands.Cog.listener("on_message")
    async def on_message_event(self, message):
        with contextlib.suppress(discord.HTTPException):
            if message.content in (f'<@{self.bot.user.id}>', f'<@!{self.bot.user.id}>'):
                display_prefixes = [f'`{p}`' for p in DEFAULT_PREFIXES]
                await message.reply(
                    f"Hi **{message.author.name}**, my prefixes are "
                    f"{', '.join(display_prefixes[0:-1]) if len(display_prefixes) > 1 else display_prefixes[0]}"
                    f"{' and ' + display_prefixes[-1] if len(display_prefixes) > 1 else ''}.\n"
                    "However you will only be able to run a command by using slash commands `/`. <:ty:833356132075700254>",
                    mention_author=False
                )

    def format_log_embed(self, guild, title, who_added=None):
        embed = discord.Embed(timestamp=discord.utils.utcnow(), colour=self.bot.colour, title=title)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Name", value=guild.name, inline=False)
        embed.add_field(name="ID", value=str(guild.id), inline=False)
        embed.add_field(name="Owner", value=str(guild.owner) + " | " + str(guild.owner.id), inline=False)
        embed.add_field(name="Members", value=len(guild.members), inline=False)
        embed.add_field(name="Bots", value=len(guild.bots), inline=False)
        embed.add_field(name="Humans", value=len(guild.humans), inline=False)
        embed.add_field(name="Bots/Humans", value=round(len(guild.bots) / len(guild.humans), 2), inline=False)
        if who_added:
            embed.set_footer(icon_url=who_added.display_avatar.url, text=str(who_added))
        return embed

    @commands.Cog.listener("on_guild_join")
    async def on_guild_join(self, guild):
        who_added = None
        try:
            async for log in guild.audit_logs(limit=10):
                if log.action == discord.AuditLogAction.bot_add:
                    if log.target == self.bot.user:
                        who_added = log.user
        except discord.Forbidden:
            pass
        embed = self.format_log_embed(guild, "I joined a new Guild", who_added=who_added)
        if self.bot.log_channel_id:
            await self.bot.get_channel(self.bot.log_channel_id).send(embed=embed)

    @commands.Cog.listener("on_guild_remove")
    async def on_guild_remove(self, guild):
        embed = self.format_log_embed(guild, "I was removed from a Guild")
        if self.bot.log_channel_id:
            await self.bot.get_channel(self.bot.log_channel_id).send(embed=embed)
