import datetime
from typing import Literal

import discord
from discord.ext import commands

from utils import defaults
from utils.context import AyaneContext
from utils.cache import ExpiringCache
from main import Ayane

from collections import defaultdict


class MessageContentCooldown(commands.CooldownMapping):
    def _bucket_key(self, message):
        return message.channel.id, message.content


class AntiSpam:
    """We use the same ratelimit/criteria as https://github.com/Rapptz/RoboDanny/"""

    def __init__(self):
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
        # Make sure the member isn't already kicked/banned
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

    async def sanction_if_spamming(self, message, is_strict_mode):
        if not message.guild or is_strict_mode is None:
            return
        if self.is_spamming(message):
            if is_strict_mode:
                await self.sanction(message.author, "ban", "Strict-mode")
            else:
                await self.sanction(message.author, "kick", "Soft-mode")


def setup(bot):
    bot.add_cog(Moderator(bot))


class Moderator(defaults.AyaneCog, emoji='<:moderator:846464409404440666>', brief='The bot moderator commands.'):
    def __init__(self, bot):
        self.bot: Ayane = bot
        # We use defaultdict because it's faster than using setdefault each time.
        self.antispam = defaultdict(AntiSpam)

    async def get_guild_mod(self, guild_id):
        return await self.bot.db.fetchval("SELECT strict_antispam FROM registered_guild WHERE id=$1", guild_id)

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
        if message.author.guild_permissions.manage_messages:
            return
        guild_mode = await self.get_guild_mod(message.guild.id)
        await self.antispam[message.guild.id].sanction_if_spamming(message, guild_mode)


    @defaults.ayane_command(name="antispam", aliases=["antiraid"])
    @commands.has_guild_permissions(kick_members=True, ban_members=True, manage_messages=True)
    async def toggle_antispam(
            self,
            ctx: AyaneContext,
            mode: Literal["soft", "strict", "off"] = commands.Option(
                default="off",
                description="The guild antispam mode",
            ),
    ) -> discord.Message:
        """Set the antispam mode
        `strict` : ban users when spamming
        `soft` : kick users when spamming
        `off` : disable anti-spam
        default to `off`."""
        if mode == "off":
            antispam_mode = None
        else:
            antispam_mode = mode == "strict"
        await self.bot.db.execute(
            "INSERT INTO registered_guild (id,name,strict_antispam)"
            "VALUES ($1,$2,$3) ON CONFLICT (id) DO UPDATE SET name=$2,strict_antispam=$3",
            ctx.guild.id,
            ctx.guild.name,
            antispam_mode,
        )
