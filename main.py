import io
import os
import logging
import traceback
import contextlib
import humanize

import aiohttp
import certifi
import ssl

import asyncpg
import discord
import waifuim

from discord.ext import commands
from discord import app_commands

from utils import constants, exceptions
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

class AyaneCommandTree(app_commands.CommandTree):
    async def on_error(
        self,
        interaction,
        command,
        error,
    ) -> None:
        """Handles command exceptions and logs unhandled ones to the support guild."""
        if hasattr(command, 'on_error') and not hasattr(interaction, 'bypass_first_error_handler'):
            return
    
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        ignored = [
                      commands.CommandNotFound,
                  ] + ([commands.CheckFailure] if LOCAL else [])
        if isinstance(error, tuple(ignored)):
            return
        
        if isinstance(error, commands.UserInputError):
            embed = discord.Embed(title='An incorrect argument was passed.')
    
            if isinstance(error, exceptions.UserLocked):
                embed.title = '❌ Multiples Commands Running'
                embed.description = f"Hey **{interaction.user}**,one thing after an other. " + str(error)
    
            elif isinstance(error, commands.BadUnionArgument):
                embed.description = f"You did not provide a valid {conv_n(error.converters)}, please go check `/help {command.name}`."
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
                    embed.description = f"You did not provide a valid user, please go check `/help {command.name}`."
                    embed.title = "❌ User not found"
    
                elif isinstance(error, commands.MemberNotFound):
                    embed.description = f"You did not provide a valid member, Please go check `/help {command.name}`."
                    embed.title = "❌ Member not found"
    
                elif isinstance(error, commands.RoleNotFound):
                    embed.description = f"You did not provide a valid role, Please go check `/help {command.name}`."
                    embed.title = "❌ Role not found"
    
                else:
                    embed.description = f"You provided at least one wrong argument. Please go check `/help {command.name}`"
                    embed.title = "❌ Bad argument"
    
            else:
                embed.description = f"You made an error in your commmand. Please go check `/help {command.name}`"
                embed.title = "❌ Input error"
    
            await interaction.client.send_interaction_error_message(embed=embed, delete_after=15)
    
        elif isinstance(error, commands.BotMissingPermissions):
            missing = [(e.replace('_', ' ').replace('guild', 'server')).title() for e in error.missing_permissions]
            perms_formatted = "**, **".join(missing[:-2] + ["** and **".join(missing[-2:])])
            _message = f"I need the **{perms_formatted}** permission(s) to run this command."
            embed = discord.Embed(title="❌ Bot missing permissions", description=_message)
            await interaction.client.send_interaction_error_message(embed=embed)
    
        elif isinstance(error, commands.DisabledCommand):
            if command.enabled:
                _message = str(error)
            else:
                _message = f"`{command.name}` command has been temporally disabled, it is probably under maintenance. For more information join the [support server]({constants.server_invite})!"
            embed = discord.Embed(title="🛑 Command disabled", description=_message)
            await interaction.client.send_interaction_error_message(embed=embed, delete_after=15)
    
        elif isinstance(error, commands.MaxConcurrencyReached):
            _message = f"This command can only be used **{error.number}** time simultaneously, please retry later."
            embed = discord.Embed(title="🛑 Maximum concurrency reached", description=_message)
            await interaction.client.send_interaction_error_message(embed=embed, delete_after=15)
    
        elif isinstance(error, commands.CommandOnCooldown):
            _message = f"This command is on cooldown, please retry in {humanize.time.precisedelta(math.ceil(error.retry_after))}."
            embed = discord.Embed(title="🛑 Command on cooldown", description=_message)
            await interaction.client.send_interaction_error_message(embed=embed, delete_after=15)
    
        elif isinstance(error, commands.MissingPermissions):
            missing = [(e.replace('_', ' ').replace('guild', 'server')).title() for e in error.missing_permissions]
            perms_formatted = "**, **".join(missing[:-2] + ["** and **".join(missing[-2:])])
            _message = f"You need the **{perms_formatted}** permission(s) to use this command."
            embed = discord.Embed(title="🛑 Missing permissions", description=_message)
            await interaction.client.send_interaction_error_message(embed=embed, delete_after=15)
    
        elif isinstance(error, commands.MissingRole):
            missing = error.missing_role
            _message = f"You need the **{missing}** role to use this command."
            embed = discord.Embed(title="🛑 Missing role", description=_message)
            await interaction.client.send_interaction_error_message(embed=embed, delete_after=15)
    
        elif isinstance(error, discord.Forbidden):
            _message = "I dont have the permissions to run this command."
            embed = discord.Embed(title="❌ Permission error", description=_message)
            await interaction.client.send_interaction_error_message(embed=embed)
    
        elif isinstance(error, commands.NSFWChannelRequired):
            _message = "Sorry, I cannot display **NSFW** content in this channel."
            embed = discord.Embed(title="🛑 NSFW channel required", description=_message)
            await interaction.client.send_interaction_error_message(embed=embed, delete_after=15)
    
        elif isinstance(error, commands.NoPrivateMessage):
            return
    
        elif isinstance(error, commands.NotOwner):
            embed = discord.Embed(
                title="🛑 Owner-only",
                description=f"Sorry **{interaction.user}**, but this commmand is an owner-only command and "
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
            await interaction.client.send_interaction_error_message(embed=embed, delete_after=15)
    
        else:
            await interaction.client.send_unexpected_error(interaction, command, error)


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
            intents=intents
        )

        self.server_invite = constants.server_invite
        self.owner_ids = OWNER_IDS
        self.colour = self.color = discord.Colour(value=0xA37FFF)

        # Startup tasks and stuff
        self.loop.create_task(self.on_ready_once())
        self.loop.run_until_complete(self.before_ready_once())
        self._load_cogs()
        self.db: asyncpg.Pool = self.loop.run_until_complete(self._establish_database_connection())
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
        self.verified_message_command_guilds = [336642139381301249, 800449566037114892]
        self.verified_slash_command_guilds = []
        print(self.owner_ids)
        self.verified_message_command_user_ids = [*self.owner_ids]
        self.verified_slash_command_user_ids = []
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
        cog_name = command.cog.qualified_name.lower() if command.cog else None
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
        ssl_context = ssl.create_default_context(cafile=certifi.where())
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
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="Hentai! 🍑"
            )
        )


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
        if LOCAL is False or (LOCAL is True and PREVENT_LOCAL_COMMANDS is False):
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

        if LOCAL:
            local_data = f'\nError occured in local mode with user of "from {LOCAL_USER}"'
        else:
            local_data = ''

        to_send = (
            f"```yaml\n{command_data}``````py"
            f"\nCommand {command} raised the following error:{local_data}"
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
                    f"```yaml\n{command_data}``````py Command {command} raised the following error:{local_data}\n```",
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
