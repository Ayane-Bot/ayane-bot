import io
import os
import logging
import contextlib
import traceback

import aiohttp
import certifi
import ssl

import asyncpg
import discord
import waifuim

from discord.ext import commands
from discord import app_commands

from utils import constants
from utils.context import AyaneContext
from utils.exceptions import UserBlacklisted, string_map, join_literals, convert_union_annotations, conv_n
from utils.helpers import PersistentExceptionView
from private.config import (TOKEN, DEFAULT_PREFIXES, OWNER_IDS, LOCAL, DB_CONF, WEBHOOK_URL, WAIFU_API_TOKEN,
                            PREVENT_LOCAL_COMMANDS)
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
        self.pool = None
        self.invite: str = None
        self.waifu_client: waifuim.WaifuAioClient = None
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
            intents=intents
        )

        self.server_invite = constants.server_invite
        self.owner_ids = OWNER_IDS
        self.colour = self.color = discord.Colour(value=0xA37FFF)

        # Startup tasks and stuff
        self._load_cogs()
        self.user_lock = {}
        self.guild_ratio = 0.35
        self.guild_maxbot = 31
        self.minimum_command_interval = 86400
        self.log_channel_id = 921577029546164325
        self.guild_whitelist = [
            110373943822540800,
            264445053596991498,
            333949691962195969,
            336642139381301249,
            800449566037114892,
            508355356376825868,
            850807820634030130,
        ]
        self.default_checks = {self.check_blacklisted,self.check_user_lock}

    def get_sus_guilds(self):
        sus = []
        for guild in self.guilds:
            guild_bots = [m for m in guild.members if m.bots]
            ratio = len(guild_bots) / len(guild.members)
            if (
                    ratio > self.guild_ratio
                    or len(guild_bots) > self.guild_maxbot
                    and guild.id not in self.guild_whitelist
            ):
                sus.append(guild)
        return sus

    def add_user_lock(self, lock: UserLock):
        self.user_lock.update({lock.user.id: lock})

    @staticmethod
    async def check_user_lock(interaction):
        if lock := interaction.client.user_lock.get(interaction.user.id):
            if lock.locked():
                if isinstance(lock, UserLock):
                    raise lock.error
                raise app_commands.AppCommandError(
                    "You can't invoke another command while another command is running."
                )
            else:
                interaction.client.user_lock.pop(interaction.user.id, None)
                return True
        return True

    @staticmethod
    async def check_blacklisted(interaction):
        cog_name = interaction.command.cog.qualified_name.lower() if interaction.command.cog else None
        if "jishaku" == cog_name:
            return True
        if not hasattr(interaction.client, "pool"):
            return True
        result = await interaction.client.is_blacklisted(interaction.user)
        if result:
            raise UserBlacklisted(interaction.user, reason=result)
        return True

    async def is_blacklisted(self, user):
        return await self.pool.fetchval("SELECT reason FROM registered_user WHERE id=$1 AND is_blacklisted", user.id)

    async def setup_hook(self) -> None:
        self.pool = await self.establish_database_connection()
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        self.waifu_client = waifuim.WaifuAioClient(appname="Ayane-Bot", token=WAIFU_API_TOKEN, session=self.session)

    async def on_ready_once(self):
        await self.wait_until_ready()
        self.invite = discord.utils.oauth_url(self.user.id,
                                              permissions=discord.Permissions(173211516614),
                                              redirect_uri=self.server_invite,
                                              scopes=["bot", "applications.commands"])
        self.add_view(PersistentExceptionView(self))
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="Hentai! 🍑"
            )
        )


    @staticmethod
    async def establish_database_connection() -> asyncpg.Pool:
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
            
    @staticmethod
    async def send_interaction_error_message(interaction, *args, **kwargs):
        if interaction.response.is_done():
            await interaction.followup.send(*args, **kwargs)

        else:
            await interaction.response.send_message(*args, **kwargs)

    @staticmethod
    async def send_unexpected_error(interaction, command, error, **kwargs):
        with contextlib.suppress(discord.HTTPException):
            _message = f"Sorry, an error has occured, it has been reported to my developers. To be inform of the " \
                       f"bot issues and updates join the [support server]({constants.server_invite}) !"
            embed = discord.Embed(title="❌ Error", colour=interaction.client.colour, description=_message)
            embed.add_field(name="Traceback :", value=f"```py\n{type(error).__name__} : {error}```")
            await interaction.client.get_cog("Events").send_interaction_error_message(interaction, embed=embed, **kwargs)

        error_channel = interaction.client.get_channel(920086735755575327)
        traceback_string = "".join(traceback.format_exception(etype=None, value=error, tb=error.__traceback__))

        if interaction.guild:
            command_data = (
                f"by: {interaction.user} ({interaction.user.id})"
                f"\ncommand: {command}"
                f"\nguild_id: {interaction.guild.id} - channel_id: {interaction.channel.id}"
                f"\nowner: {interaction.guild.owner.name} ({interaction.guild.owner.id})"
                f"\nbot admin: {'✅' if interaction.guild.me.guild_permissions.administrator else '❌'} "
                f"- role pos: {interaction.guild.me.top_role.position}"
            )
        else:
            command_data = (
                f"command: {command}"
                f"\nCommand executed in DMs"
            )

        to_send = (
            f"```yaml\n{command_data}``````py"
            f"\nCommand {command} raised the following error:"
            f"\n{traceback_string}\n```"
        )

        try:
            if len(to_send) < 2000:
                await error_channel.send(to_send, view=PersistentExceptionView(interaction.client))
            else:
                file = discord.File(
                    io.StringIO(traceback_string), filename="traceback.py"
                )
                await error_channel.send(
                    f"```yaml\n{command_data}``````py Command {command} raised the following error:\n```",
                    file=file,
                    view=PersistentExceptionView(interaction.client),
                )
        finally:
            for line in traceback_string.split("\n"):
                logging.info(line)

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
    try:
        webhook = discord.SyncWebhook.from_url(WEBHOOK_URL, bot_token=bot.http.token)
        webhook.send('👋 Ayane is waking up!')
        del webhook
        async with bot:
            await bot.start(TOKEN)
            await bot.on_ready_once()
    finally:
        webhook = discord.SyncWebhook.from_url(WEBHOOK_URL, bot_token=bot.http.token)
        webhook.send('🔻 Ayane is going to sleep!')
