import os
import logging

import asyncpg
import discord

from discord.ext import commands

from private.config import (TOKEN, DEFAULT_PREFIXES, OWNER_IDS, LOCAL, DB_CONF)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)-15s] %(message)s")


class Ayane(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(*DEFAULT_PREFIXES),
            strip_after_prefix=True,
            intents=discord.Intents.all())
        self.loop.create_task(self._set_bot_attrs())
        self._load_cogs()
        self.db: asyncpg.Pool = self.loop.run_until_complete(self._establish_database_connection())
        self.owner_ids = OWNER_IDS
        self.website = "https://ayane.live/"
        self.server_invite = "https://discord.gg/QNXC8yFfKg"
        self.colour = discord.Colour(value=0xA37FFF)

    async def _set_bot_attrs(self):
        await self.wait_until_ready()
        self.invite = discord.utils.oauth_url(self.user.id, permissions=discord.Permissions(173211516614), redirect_uri=self.server_invite, scopes=["bot", "applications.commands"])

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
