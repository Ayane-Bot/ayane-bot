import asyncio
import io
import os
import logging
import ssl
import traceback

import aiohttp
import certifi
import ssl
import humanize

import asyncpg
import discord
import waifuim

from discord.ext import commands

from utils import constants
from utils.context import AyaneContext
from utils.exceptions import UserBlacklisted
from utils.helpers import PersistentExceptionView
from private.config import (TOKEN, DEFAULT_PREFIXES, OWNER_IDS, LOCAL, DB_CONF, WEBHOOK_URL, WAIFU_API_TOKEN)
from utils.lock import UserLock

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
        self.waifuclient: waifuim.WaifuAioClient = None
        self.session: aiohttp.ClientSession = None

        # All extensions that are not located in the 'cogs' directory.
        self.initial_extensions = ['jishaku']

        # Disabling the typing intents as we won't be using them.
        intents = discord.Intents.all()
        intents.typing = False  # noqa
        intents.dm_typing = False  # noqa

        super().__init__(
            command_prefix=commands.when_mentioned_or(*DEFAULT_PREFIXES),
            strip_after_prefix=True,
            intents=intents,
        )

        self.server_invite = constants.server_invite
        self.owner_ids = OWNER_IDS
        self.colour = self.color = discord.Colour(value=0xA37FFF)

        # Startup tasks and stuff
        self.loop.create_task(self.on_ready_once())
        self.loop.run_until_complete(self.before_ready_once())
        self._load_cogs()
        self.db: asyncpg.Pool = self.loop.run_until_complete(self._establish_database_connection())
        self.sus_guilds = []
        self.user_lock = {}
        self.guild_ratio = 0.35
        self.guild_maxbot = 31
        self.minimum_command_interval = 86400
        self.guild_whitelist = [
            110373943822540800,
            264445053596991498,
            333949691962195969,
            336642139381301249,
            800449566037114892,
            508355356376825868,
            850807820634030130,
        ]
        self.add_check(self.check_blacklisted)
        self.add_check(self.check_user_lock)

    def get_sus_guilds(self):
        sus = []
        for guild in self.guilds:
            prct = len(guild.bots) / len(guild.members)
            if (
                    prct > self.guild_ratio
                    or len(guild.bots) > self.guild_maxbot
                    and guild.id not in self.guild_whitelist
            ):
                sus.append(guild)
        return sus

    async def wait_commands(self, guild):
        try:
            await self.wait_for(
                "command_completion", timeout=self.minimum_command_interval
            )
        except asyncio.TimeoutError:

            if guild.id not in [g.id for g in self.get_sus_guilds()]:
                return
            guild = self.get_guild(guild.id)
            prct = len(guild.bots) / len(guild.members)
            try:
                await guild.owner.send(
                    f"""Hey **{guild.owner.name}** looks like someone invited me in your server but I have a bad news...
    Discord does not like servers with too many bots or with a too big proportion of them in the server, also it seems that no one used me in your server for at least {humanize.time.precisedelta(self.minimum_command_interval)}, therefore I have to leave your server.
    I'm really sorry but don't worry too much, once the bot has been verified (keep a look out for the checkmark) you can reinvite it and everything will be fine.
    Alternatively you can also decide to make your server respect some condions that will avoid me to leave after {humanize.time.precisedelta(self.minimum_command_interval)}.
    (less than **{self.guild_maxbot}** bots in your server and a bots/guild_members ratio less or equal to **{self.guild_ratio * 100}%**)

    **Here is some information that may help you to understand my decision.**
    *Those information were calculated taking my presence in your server in account.*

    You had **{len(guild.bots)}** bots in your server and a ratio of bots/user of **{round(prct * 100, 2)}**%"""
                )

            except:  # noqa
                pass

            self.sus_guilds.append(guild.id)
            await guild.leave()

    def add_user_lock(self, lock: UserLock):
        self.user_lock.update({lock.user.id: lock})

    @staticmethod
    async def check_user_lock(ctx):
        if lock := ctx.bot.user_lock.get(ctx.author.id):
            if lock.locked():
                if isinstance(lock, UserLock):
                    raise lock.error
                raise commands.CommandError(
                    "You can't invoke another command while another command is running."
                )
            else:
                ctx.bot.user_lock.pop(ctx.author.id, None)
                return True
        return True

    @staticmethod
    async def check_blacklisted(ctx):
        cog_name = ctx.command.cog.qualified_name.lower() if ctx.command.cog else None
        if "jishaku" == cog_name:
            return True
        if not hasattr(ctx.bot, "db"):
            return True
        result = await ctx.bot.is_blacklisted(ctx.author)
        if result:
            raise UserBlacklisted(ctx.author, reason=result[0])
        return True

    async def is_blacklisted(self, user):
        return await self.db.fetchrow("SELECT reason FROM registered_user WHERE id=$1 AND is_blacklisted", user.id)

    async def before_ready_once(self):
        ssl_context=ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        self.waifuclient = waifuim.WaifuAioClient(appname="Ayane-Bot", token=WAIFU_API_TOKEN, session=self.session)

    async def on_ready_once(self):
        await self.wait_until_ready()
        self.invite = discord.utils.oauth_url(self.user.id,
                                              permissions=discord.Permissions(173211516614),
                                              redirect_uri=self.server_invite,
                                              scopes=["bot", "applications.commands"])
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

    async def on_interaction(self, interaction: discord.Interaction):
        try:
            await super().on_interaction(interaction)
        except commands.CommandNotFound as error:
            print(error)

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
