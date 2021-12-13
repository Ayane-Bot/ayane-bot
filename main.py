import io
import os
import logging
import traceback

import asyncpg
import discord

from discord.ext import commands

from cogs.utils.helpers import PersistentExceptionView
from private.config import (TOKEN, DEFAULT_PREFIXES, OWNER_IDS, LOCAL, DB_CONF)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)-15s] %(message)s")


class Ayane(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(*DEFAULT_PREFIXES),
            strip_after_prefix=True,
            intents=discord.Intents.all())
        self.invite: str = None

        self.error_view: discord.ui.View = None
        self.owner_ids = OWNER_IDS

        # Constants- should be moved to cogs/utils/constants.py maybe?
        self.website = "https://ayane.live/"
        self.server_invite = "https://discord.gg/QNXC8yFfKg"
        self.colour = discord.Colour(value=0xA37FFF)

        # Startup tasks and stuff
        self.loop.create_task(self.on_ready_once())
        self._load_cogs()
        self.db: asyncpg.Pool = self.loop.run_until_complete(self._establish_database_connection())

    async def on_ready_once(self):
        await self.wait_until_ready()
        self.invite = discord.utils.oauth_url(self.user.id, permissions=discord.Permissions(173211516614), redirect_uri=self.server_invite, scopes=["bot", "applications.commands"])
        self.error_view = PersistentExceptionView(self)
        self.add_view(self.error_view)

    @staticmethod
    async def _establish_database_connection() -> asyncpg.Pool:
        credentials = {
            "user": DB_CONF.user,
            "password": DB_CONF.password,
            "database": DB_CONF.db,
            "host": DB_CONF.host,
            "port": DB_CONF.port
        }
        try:
            return await asyncpg.create_pool(**credentials)
        except Exception as e:
            logging.error("Could not create database pool", exc_info=e)
        finally:
            logging.info('Database connection created.')

    async def on_ready(self):
        print("Logged in as", str(self.user))

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        traceback_string = traceback.format_exc()
        for line in traceback_string.split('\n'):
            logging.info(line)
        await self.wait_until_ready()
        error_channel = self.get_channel(920086768903147550)
        to_send = f"```yaml\nAn error occurred in an {event_method} event``````py" \
                  f"\n{traceback_string}\n```"
        if len(to_send) < 2000:
            try:
                await error_channel.send(to_send)

            except (discord.Forbidden, discord.HTTPException):

                await error_channel.send(f"```yaml\nAn error occurred in an {event_method} event``````py",
                                         file=discord.File(io.StringIO(traceback_string), filename='traceback.py'))
        else:
            await error_channel.send(f"```yaml\nAn error occurred in an {event_method} event``````py",
                                     file=discord.File(io.StringIO(traceback_string), filename='traceback.py'))

    def _load_cogs(self):
        """
        Loads all the extensions in the ./cogs directory.
        """
        try:
            self.load_extension("jishaku")
        except Exception as e:
            logging.error(f"Failed to load jishaku", exc_info=e)

        for ext in os.listdir("./cogs"):
            if ext.endswith(".py"):
                try:
                    self.load_extension(f"cogs.{ext[:-3]}")
                except Exception as e:
                    logging.error(f"Failed to load extension {ext}.", exc_info=e)


if __name__ == "__main__":
    bot = Ayane()

    @bot.check
    async def running_locally(ctx):
        """
        If the bot is running locally, only allows the owner
        defined in the private/config.py to use commands.
        """
        if LOCAL is False:
            return True
        return await bot.is_owner(ctx.author)

    bot.run(TOKEN)
