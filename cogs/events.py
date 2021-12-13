import contextlib
import io
import logging
import traceback

import discord
from discord.ext import commands

from main import Ayane
from private.config import LOCAL


def setup(bot):
    bot.add_cog(Events(bot))


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot: Ayane = bot

    @commands.Cog.listener('on_command_error')
    async def error_log(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        ignored = [commands.CommandNotFound,
                   ] + [commands.NotOwner] if LOCAL else []

        if isinstance(error, tuple(ignored)):
            return

        elif isinstance(error, commands.CheckFailure):
            return await ctx.send(f"❌ Sorry, you aren't allowed to run this command.")

        elif isinstance(error, commands.UserInputError):
            return await ctx.send(str(error))

        else:
            with contextlib.suppress(discord.HTTPException):
                await ctx.send(f"❌ Sorry, an unexpected error occurred while running this command.")
            error_channel = self.bot.get_channel(920086735755575327)
            traceback_string = "".join(traceback.format_exception(etype=None, value=error, tb=error.__traceback__))

            if ctx.guild:
                command_data = f"by: {ctx.author.name} ({ctx.author.id})" \
                               f"\ncommand: {ctx.message.content[0:1700]}" \
                               f"\nguild_id: {ctx.guild.id} - channel_id: {ctx.channel.id}" \
                               f"\nowner: {ctx.guild.owner.name} ({ctx.guild.owner.id})" \
                               f"\nbot admin: {'✅' if ctx.me.guild_permissions.administrator else '❌'} " \
                               f"- role pos: {ctx.me.top_role.position}"
            else:
                command_data = f"command: {ctx.message.content[0:1700]}" \
                               f"\nCommand executed in DMs"

            to_send = f"```yaml\n{command_data}``````py\n{ctx.command} " \
                      f"command raised an error:\n{traceback_string}\n```"

            try:
                if len(to_send) < 2000:
                    await error_channel.send(to_send, view=self.bot.error_view)
                else:
                    file = discord.File(io.StringIO(traceback_string), filename='traceback.py')
                    await error_channel.send(f"```yaml\n{command_data}``````py Command: {ctx.command}raised the following error:\n```",
                                             file=file, view=self.bot.error_view)
            finally:
                for line in traceback_string.split('\n'):
                    logging.info(line)

