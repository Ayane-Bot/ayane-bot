import io
import os
import logging
import traceback

import asyncpg
import discord

from discord.ext import commands

from cogs.utils.context import AyaneContext
from cogs.utils.helpers import PersistentExceptionView
from private.config import (TOKEN, DEFAULT_PREFIXES, OWNER_IDS, LOCAL, DB_CONF, WEBHOOK_URL)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)-15s] %(message)s")

# Some very fancy characters hehe
err = '\033[41m\033[30m❌\033[0m'
oop = '\033[43m\033[37m⚠\033[0m'
ok = '\033[42m\033[30m✔\033[0m'


# Jishaku flags
os.environ['JISHAKU_NO_UNDERSCORE'] = 'True'
os.environ['JISHAKU_HIDE'] = 'True'


class Ayane(commands.Bot):
    def __init__(self):
        # These are all attributes that will be set later in the `on_ready_once` method.
        self.invite: str = None

        # All extensions that are not located in the 'cogs' directory.
        self.initial_extensions = ['jishaku']

        super().__init__(
            command_prefix=commands.when_mentioned_or(*DEFAULT_PREFIXES),
            strip_after_prefix=True,
            intents=discord.Intents.all())

        self.owner_ids = OWNER_IDS
        self.colour = discord.Colour(value=0xA37FFF)

        # Startup tasks and stuff
        self.loop.create_task(self.on_ready_once())
        self._load_cogs()
        self.db: asyncpg.Pool = self.loop.run_until_complete(self._establish_database_connection())

    async def on_ready_once(self):
        await self.wait_until_ready()
        self.invite = discord.utils.oauth_url(self.user.id, permissions=discord.Permissions(173211516614), redirect_uri=self.server_invite, scopes=["bot", "applications.commands"])
        self.add_view(PersistentExceptionView(self))

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
            logging.info(f'{ok} Database connection created.')

    async def on_ready(self):
        logging.info(f"\033[42m\033[35m Logged in as {self.user}! \033[0m")

    async def get_context(self, message, *, cls=AyaneContext):
        return await super().get_context(message, cls=cls)

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        """ Logs uncaught exceptions and sends them to the error log channel in the support guild. """
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
        extensions = [f"cogs.{f[:-3]}" for f in os.listdir("./cogs") if f.endswith(".py")  # 'Cogs' folder
                      ] + self.initial_extensions  # Initial extensions like jishaku or others that may be elsewhere
        for ext in extensions:
            try:
                self.load_extension(ext)
                logging.info(f"{ok} Loaded extension {ext}")
                
            except Exception as e:
                if isinstance(e, commands.ExtensionNotFound):
                    logging.error(f"{oop} Extension {ext} was not found {oop}", exc_info=False)
                    
                elif isinstance(e, commands.NoEntryPointError):
                    logging.error(f"{err} Extension {ext} has no setup function {err}", exc_info=False)
                    
                else:
                    logging.error(f"{err}{err} Failed to load extension {ext} {err}{err}", exc_info=e)


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
        
        if await bot.is_owner(ctx.author):
            return True
        raise commands.NotOwner()

    try:
        if not LOCAL:
            webhook = discord.SyncWebhook.from_url(WEBHOOK_URL, bot_token=bot.http.token)
            webhook.send('👋 Ayane is waking up!')
            del webhook
        bot.run(TOKEN)
        
    finally:
        if not LOCAL:
            webhook = discord.SyncWebhook.from_url(WEBHOOK_URL, bot_token=bot.http.token)
            webhook.send('🔻 Ayane is going to sleep!')
