import contextlib
import inspect
import io
import logging
import math
import traceback
import typing

import discord
import humanize as humanize
from discord.ext import commands

from utils import constants, defaults, exceptions
from utils.helpers import PersistentExceptionView
from main import Ayane
from private.config import LOCAL, LOCAL_USER, DEFAULT_PREFIXES

async def setup(bot):
    bot.add_cog(Events(bot))


class Events(defaults.AyaneCog, emoji='⚙', brief='Ayane Internal Stuff'):
    def __init__(self, bot):
        self.bot: Ayane = bot

    @commands.Cog.listener("on_command")
    async def basic_command_logger(self, ctx):
        await self.bot.db.execute(
            "INSERT INTO commands (guild_id, user_id, command, timestamp) VALUES ($1, $2, $3, $4)",
            getattr(ctx.guild, "id", None),
            ctx.author.id,
            ctx.command.qualified_name,
            ctx.message.created_at,
        )

    @commands.Cog.listener("on_message")
    async def on_message_event(self, message):
        with contextlib.suppress(discord.HTTPException):
            if message.content in (f'<@{self.bot.user.id}>', f'<@!{self.bot.user.id}>'):
                display_prefixes = [f'`{p}`' for p in DEFAULT_PREFIXES]
                await message.reply(
                    f"Hi **{message.author.name}**, my prefixes are "
                    f"{', '.join(display_prefixes[0:-1]) if len(display_prefixes) > 1 else display_prefixes[0]}"
                    f"{' and ' + display_prefixes[-1] if len(display_prefixes) > 1 else ''}.\n"
                    "However you will only be able to run a command by using slash commands `/`. <:ty:833356132075700254>",
                    mention_author=False
                )

    def format_log_embed(self, guild, title, who_added=None):
        embed = discord.Embed(timestamp=discord.utils.utcnow(), colour=self.bot.colour, title=title)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Name", value=guild.name, inline=False)
        embed.add_field(name="ID", value=str(guild.id), inline=False)
        embed.add_field(name="Owner", value=str(guild.owner) + " | " + str(guild.owner.id), inline=False)
        embed.add_field(name="Members", value=len(guild.members), inline=False)
        embed.add_field(name="Bots", value=len(guild.bots), inline=False)
        embed.add_field(name="Humans", value=len(guild.humans), inline=False)
        embed.add_field(name="Bots/Humans", value=round(len(guild.bots) / len(guild.humans), 2), inline=False)
        if who_added:
            embed.set_footer(icon_url=who_added.display_avatar.url, text=str(who_added))
        return embed

    @commands.Cog.listener("on_guild_join")
    async def on_guild_join(self, guild):
        who_added = None
        try:
            async for log in guild.audit_logs(limit=10):
                if log.action == discord.AuditLogAction.bot_add:
                    if log.target == self.bot.user:
                        who_added = log.user
        except discord.Forbidden:
            pass
        embed = self.format_log_embed(guild, "I joined a new Guild", who_added=who_added)
        if self.bot.log_channel_id:
            await self.bot.get_channel(self.bot.log_channel_id).send(embed=embed)

    @commands.Cog.listener("on_guild_remove")
    async def on_guild_remove(self, guild):
        embed = self.format_log_embed(guild, "I was removed from a Guild")
        if self.bot.log_channel_id:
            await self.bot.get_channel(self.bot.log_channel_id).send(embed=embed)
