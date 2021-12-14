import contextlib
import io
import logging
import math
import traceback

import discord
import humanize as humanize
from discord.ext import commands

from main import Ayane
from private.config import LOCAL, LOCAL_USER


def setup(bot):
    bot.add_cog(Events(bot))


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


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot: Ayane = bot

    @commands.Cog.listener("on_command_error")
    async def error_log(self, ctx, error):
        """Handles command exceptions and logs unhandled ones to the support guild."""

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        ignored = [
                      commands.CommandNotFound,
                  ] + ([commands.CheckFailure] if LOCAL else [])

        if isinstance(error, tuple(ignored)):
            return

        elif isinstance(error, commands.BadUnionArgument):
            _message = f"You did not provide a valid {conv_n(error.converters)}, please go check `{ctx.clean_prefix}help {ctx.command.name}`."
            embed = discord.Embed(title="❌ Bad argument", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.BadArgument):
            _message = f"You provided at least one wrong argument. Please go check `{ctx.clean_prefix}help {ctx.command}`"
            embed = discord.Embed(title="❌ Bad argument", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.UserNotFound):
            _message = f"You did not provide a valid user, please go check `{ctx.clean_prefix}help {ctx.command.name}`."
            embed = discord.Embed(title="❌ User not found", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.MemberNotFound):
            _message = f"You did not provide a valid member, Please go check `{ctx.clean_prefix}help {ctx.command.name}`."
            embed = discord.Embed(title="❌ Member not found", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.UserInputError):
            _message = f"You made an error in your commmand. Please go check `{ctx.clean_prefix}help {ctx.command}`"
            embed = discord.Embed(title="❌ Input error", description=_message)
            await ctx.send(embed=embed, delete_after=15)

        elif isinstance(error, commands.BotMissingPermissions):
            missing = [(e.replace('_', ' ').replace('guild', 'server')).title() for e in error.missing_permissions]
            perms_formatted = "**, **".join(missing[:-2] + ["** and **".join(missing[-2:])])
            _message = f"I need the **{perms_formatted}** permission(s) to run this command."
            embed = discord.Embed(title="❌ Bot missing permissions", description=_message)
            await ctx.send(embed=embed)

        elif isinstance(error, commands.DisabledCommand):
            _message = f"This command has been temporaly disabled, it is probably under maintenance. For more informations join the [support server]({self.bot.server_invite}) !"
            embed = discord.Embed(title="🛑 Command disabled", description=_message)
            await ctx.send(embed=embed, delete_after=15)
            return
        elif isinstance(error, commands.MaxConcurrencyReached):
            _message = f"This command can only be used **{error.number}** time simultaneously, please retry later."
            embed = discord.Embed(title="🛑 Maximum concurrency reached", description=_message)
            await ctx.send(embed=embed, delete_after=15)
            return

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

        elif isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                title="🛑 Forbidden",
                description="You do not have the permissions to use this command.",
            )
            await ctx.send(embed=embed, delete_after=15)

        else:
            with contextlib.suppress(discord.HTTPException):
                _message = f"Sorry, an error has occured, it has been reported to my developers. To be inform of the " \
                           f"bot issues and updates join the [support server]({self.bot.server_invite}) !"
                embed = discord.Embed(title="❌ Error", description=_message)
                embed.add_field(name="Traceback :", value=f"```py\n{type(error).__name__} : {error}```")
                await ctx.send(embed=embed)

            error_channel = self.bot.get_channel(920086735755575327)
            traceback_string = "".join(traceback.format_exception(etype=None, value=error, tb=error.__traceback__))

            if ctx.guild:
                command_data = (
                    f"by: {ctx.author.name} ({ctx.author.id})"
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
                local_data = f'\nError occured in local mode from {LOCAL_USER}\'s computer'
            else:
                local_data = ''

            to_send = (
                f"```yaml\n{command_data}``````py"
                f"\nCommand {ctx.command} raised the following error:{local_data}"
                f"\n{traceback_string}\n```"
            )

            try:
                if len(to_send) < 2000:
                    await error_channel.send(to_send, view=self.bot.error_view)
                else:
                    file = discord.File(
                        io.StringIO(traceback_string), filename="traceback.py"
                    )
                    await error_channel.send(
                        f"```yaml\n{command_data}``````py Command {ctx.command} raised the following error:{local_data}\n```",
                        file=file,
                        view=self.bot.error_view,
                    )
            finally:
                for line in traceback_string.split("\n"):
                    logging.info(line)

    @commands.Cog.listener("on_command")
    async def basic_command_logger(self, ctx):
        await self.bot.db.execute(
            "INSERT INTO commands (guild_id, user_id, command, timestamp) VALUES ($1, $2, $3, $4)",
            getattr(ctx.guild, "id", None),
            ctx.author.id,
            ctx.command.qualified_name,
            ctx.message.created_at,
        )
