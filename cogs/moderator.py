import datetime
from collections import defaultdict
from enum import Enum
from typing import Literal, List

import dateparser
import discord
from discord.ext import commands

from main import Ayane
from utils import defaults
from utils.cache import ExpiringCache
from utils.context import AyaneContext
from utils.exceptions import AlreadyMuted, NotMuted
from utils.mods import ModUtils
from private.config import LOCAL


class MessageContentCooldown(commands.CooldownMapping):
    def _bucket_key(self, message):
        return message.channel.id, message.content


class GuildMode(Enum):
    strict = "strict"
    soft = "soft"
    light = "light"
    disabled = None


class AntiSpam:
    """We use the same ratelimit/criteria as https://github.com/Rapptz/RoboDanny/"""

    def __init__(self):
        self.modutils = ModUtils()
        # A 30 min cache for user that joined 'together'
        self.fast_followed_joiners = ExpiringCache(seconds=1800.0)
        # The date and id of the last joiner (to determine whether they are 'fast followed users')
        self.last_joiner = None
        self.escaped_first_joiner = None
        # Cooldown for 'fast followed users'
        self.cooldown_fast_followed = commands.CooldownMapping.from_cooldown(10, 12, commands.BucketType.channel)
        # Cooldown for recent account/join users
        self.cooldown_new_user = commands.CooldownMapping.from_cooldown(30, 35.0, commands.BucketType.channel)
        # Cooldown by user
        self.cooldown_user = commands.CooldownMapping.from_cooldown(10, 12.0, commands.BucketType.user)
        # Cooldown by message content
        self.cooldown_content = MessageContentCooldown.from_cooldown(15, 17.0, commands.BucketType.member)

    @staticmethod
    async def sanction(member, action, mod):
        if member.guild.get_member(member.id):
            verb = "kicked" if action == "kick" else "banned"
            reason = f"{verb.capitalize()} by {member.guild.me} Anti-Spam ({mod})."
            await getattr(member, action)(reason=reason)
            try:
                await member.send(f"Hey it looks like my Anti-Spam {verb} you from **{member.guild.name}**\n"
                                  "If you think it's an error contact the guild moderators.\n"
                                  f"```Reason: {reason}```")
            except discord.HTTPException:
                pass

    def add_fast_followed_joiner(self, member):
        """If the user that joined and the last joiner joined date is really close (3 seconds)"""
        is_fast = False
        if self.last_joiner is None:
            self.escaped_first_joiner = member.id
        elif (member.joined_at - self.last_joiner.joined_at).total_seconds() <= 3.0:
            if self.escaped_first_joiner:
                self.fast_followed_joiners[self.escaped_first_joiner.id] = True
            self.fast_followed_joiners[member.id] = is_fast = True
            self.escaped_first_joiner = None
        return is_fast

    @staticmethod
    def is_new(member):
        # If account has been created between now and 3 big months
        recent_account = member.created_at > discord.utils.utcnow() - datetime.timedelta(days=93)
        # If the user joined in the last 2 weeks
        recent_member = member.joined_at > discord.utils.utcnow() - datetime.timedelta(days=14)
        return recent_member and recent_account

    def is_spamming(self, message):
        message_creation_date = message.created_at.timestamp()
        if message.author.id in self.fast_followed_joiners:
            if self.cooldown_fast_followed.get_bucket(message).update_rate_limit(message_creation_date):
                return True
        if self.is_new(message.author):
            if self.cooldown_new_user.get_bucket(message).update_rate_limit(message_creation_date):
                return True
        if self.cooldown_user.get_bucket(message).update_rate_limit(message_creation_date):
            return True
        if self.cooldown_content.get_bucket(message).update_rate_limit(message_creation_date):
            return True

    async def sanction_if_spamming(self, message, guild_mode):
        if not message.guild or guild_mode is None:
            return
        if self.is_spamming(message):
            if guild_mode == GuildMode.strict.value:
                if message.guild.get_member(message.author.id):
                    await self.modutils.ban(
                        message.guild,
                        message.author,
                        reason=f"{message.guild.me} AntiSpam (Strict Mode)",
                    )
            elif guild_mode == GuildMode.soft.value:
                await self.modutils.kick(
                    message.author,
                    reason=f"{message.guild.me} AntiSpam (Soft Mode)",
                    delete_last_day=True,
                )
            elif guild_mode == GuildMode.light.value:
                try:
                    await self.modutils.mute(
                        message.author,
                        reason=f"{message.guild.me} AntiSpam (Light Mode)",
                        delete_last_day=True,
                    )
                except AlreadyMuted:
                    pass


def setup(bot):
    bot.add_cog(Moderator(bot))


class Moderator(defaults.AyaneCog, emoji='<:moderator:846464409404440666>', brief='The bot moderator commands.'):
    def __init__(self, bot):
        self.bot: Ayane = bot
        # We use defaultdict because it's faster than using setdefault each time.
        self.modutils = ModUtils()
        self.antispam = defaultdict(AntiSpam)

    async def get_guild_mod(self, guild_id):
        return await self.bot.db.fetchval("SELECT anti_spam_mode FROM registered_guild WHERE id=$1", guild_id)

    @commands.Cog.listener("on_message")
    async def on_message_event(self, message):
        if not message.guild:
            return
        if message.author.id in {self.bot.owner_id, *self.bot.owner_ids}:
            return
        if not isinstance(message.author, discord.Member):
            return
        if message.author.bot:
            return
        if not LOCAL:
            guild_mode = await self.get_guild_mod(message.guild.id)
            await self.antispam[message.guild.id].sanction_if_spamming(message, guild_mode)

    @defaults.ayane_command(name="antispam", aliases=["antiraid"])
    @commands.has_guild_permissions(kick_members=True, ban_members=True, manage_messages=True)
    async def toggle_antispam(
            self,
            ctx: AyaneContext,
            mode: Literal["light", "soft", "strict", "disabled"] = commands.Option(
                default="disabled",
                description="The guild antispam mode",
            ),
    ) -> discord.Message:
        """Set the antispam mode
        `strict` : ban users when spamming (recommended)
        `soft` : kick users when spamming
        `light` : Mute users when spamming
        `disabled` : disable anti-spam
        every mode do delete the user messages in the last 24 hours.
        default to `disabled`."""
        if mode == "disabled":
            mode = None
        await self.bot.db.execute(
            "INSERT INTO registered_guild (id,name,anti_spam_mode)"
            "VALUES ($1,$2,$3) ON CONFLICT (id) DO UPDATE SET name=$2,anti_spam_mode=$3",
            ctx.guild.id,
            ctx.guild.name,
            mode,
        )
        await ctx.send(f"The antispam mode is now set to `{mode if mode else 'disabled'}`.")

    @defaults.ayane_command(name="ban")
    @commands.has_guild_permissions(ban_members=True)
    async def ban_(self, ctx: AyaneContext, member: discord.Member, *, reason=None):
        """Ban a member
        If 'spam' is in the reason, all the message the member sent in the last 24 hours will be deleted.
        If you want to ban one or multiple users that are not in the guild you should use `massban` command."""
        days = 0
        if member.guild_permissions.ban_members:
            return await ctx.send("Sorry this user also has **Ban Members** permission, "
                                  "therefore I cannot allow you to ban an other staff member")
        if reason and "spam" in reason:
            days = 1
        await self.modutils.ban(member.guild, member, reason=reason, delete_message_days=days)
        await ctx.send(f"**{member.name}** has been banned.")

    @defaults.ayane_command(name="massban")
    @commands.has_guild_permissions(ban_members=True)
    async def massban_(self, ctx: AyaneContext, users: commands.Greedy[discord.User], *, reason=None):
        """Ban multiple members at once.
        If 'spam' is in the reason, all the message the user sent in the last 24 hours will be deleted."""

        if not users:
            return await ctx.send("You need to specify at least one user who you want me to ban.")

        days = 0
        if reason and "spam" in reason:
            days = 1
        ban_command = self.bot.get_command("ban")
        for user in users:
            try:
                await ban_command(ctx, user, reason=reason)
            except Exception as e:
                await ctx.send(f"Sorry, I could not ban **{user}**, here is what happened.")
                await self.bot.get_cog("Events").error_log(ctx,e)


    @defaults.ayane_command(name="softban")
    @commands.has_guild_permissions(ban_members=True)
    async def softban_(self, ctx: AyaneContext, member: discord.Member, *, reason=None):
        """Softban a member
        If 'spam' is in the reason, all the message the user sent in the last 24 hours will be deleted.
        A softban is where the user gets banned but then unbanned right after."""
        days = 0
        if member.guild_permissions.ban_members:
            return await ctx.send("Sorry this user also has **Ban Members** permission, "
                                  "therefore I cannot allow you to ban an other staff member")
        if reason and "spam" in reason:
            days = 1
        await self.modutils.ban(member.guild, member, reason=reason, delete_message_days=days)
        await self.modutils.unban(ctx.guild, member, reason=reason)
        await ctx.send(f"**{member.name}** has been soft-banned.")

    @defaults.ayane_command(name="unban")
    @commands.has_guild_permissions(ban_members=True)
    async def unban_(self, ctx: AyaneContext, user: discord.User, *, reason=None):
        """Unban a member"""
        try:
            await self.modutils.unban(ctx.guild, user, reason=reason)
        except discord.NotFound:
            return await ctx.send("This user was not banned or has already been unbanned.")
        await ctx.send(f"**{user.name}** has been unbanned.")

    @defaults.ayane_command(name="kick")
    @commands.has_guild_permissions(kick_members=True)
    async def kick_(self, ctx: AyaneContext, member: discord.Member, *, reason=None):
        """Kick a member"""
        days = 0
        if member.guild_permissions.kick_members:
            return await ctx.send("Sorry this user also has **Kick Members** permission, "
                                  "therefore I cannot allow you to kick an other staff member")
        await self.modutils.kick(member, reason=reason)
        await ctx.send(f"**{member.name}** has been kicked.")

    @defaults.ayane_command(name="masskick")
    @commands.has_guild_permissions(kick_members=True)
    async def masskick_(self, ctx: AyaneContext, users: commands.Greedy[discord.User], *, reason=None):
        """Kick multiple users at once."""
        if not users:
            return await ctx.send("You need to specify at least one user who you want me to kick.")
        kick_command = self.bot.get_command("kick")
        for user in users:
            try:
                await kick_command(ctx, user, reason=reason)
            except Exception as e:
                await ctx.send(f"Sorry, I could not kick **{user}**, here is what happened.")
                await self.bot.get_cog("Events").error_log(ctx,e)

    @defaults.ayane_command(name="mute")
    @commands.has_guild_permissions(manage_messages=True)
    async def mute_(self, ctx: AyaneContext, member: discord.Member, *, reason=None):
        """Mute a member"""
        if member.guild_permissions.manage_messages:
            return await ctx.send("Sorry this user also has **Manage Messages** permission, "
                                  "therefore I cannot allow you to mute an other staff member")
        try:
            await self.modutils.mute(member, reason=reason)
        except AlreadyMuted:
            return await ctx.send("Sorry this user is already muted.")
        await ctx.send(f"**{member.name}** has been muted.")

    @defaults.ayane_command(name="unmute")
    @commands.has_guild_permissions(manage_messages=True)
    async def unmute_(self, ctx: AyaneContext, member: discord.Member, *, reason=None):
        """Unmute a member"""
        try:
            await self.modutils.unmute(member, reason=reason)
        except NotMuted:
            return await ctx.send("Sorry this user was not muted or as already been unmuted.")
        await ctx.send(f"**{member.name}** has been unmuted.")

    @defaults.ayane_command(name="timeout")
    @commands.has_guild_permissions(moderate_members=True)
    async def timeout_(self, ctx: AyaneContext, member: discord.Member, *, until):
        """Timeout/disable timeout of a member.
        If the time you passed is invalid and the user is already timed out, then the bot will stop the timeout."""
        until = dateparser.parse(
            until,
            settings={'TO_TIMEZONE': 'UTC', 'RETURN_AS_TIMEZONE_AWARE': True, 'PREFER_DATES_FROM': 'future'},
        )
        if not member.timed_out and not until:
            return await ctx.send("I couldn't parse your date.")

        if member.guild_permissions.moderate_members:
            return await ctx.send("Sorry this user also has **Moderate Members** permission, "
                                  "therefore I cannot allow you to timeout an other staff member")
        if until and until <= ctx.message.created_at:
            return await ctx.send("Your date is in the past.")
        try:
            await member.edit(timeout_until=until)
        except discord.HTTPException:
            return await ctx.send("Something went wrong, please check that the time provided isn't more than 28 days.")
        if until:
            state = f'has been timed out and will be release {discord.utils.format_dt(until, style="R")}.'
        else:
            state = "timeout has been disabled.\n*As I couldn't parse your date and the user was already timed out, " \
                    "I disabled its timeout.*"
        await ctx.send(f"**{member.name}** {state}")
