import os
import typing

import discord
from discord.ext import commands
from discord import app_commands

from utils.context import AyaneContext
from main import Ayane
from private.config import LOCAL


async def setup(bot):
    await bot.add_cog(Owner(bot))


class Owner(commands.Cog):
    def __init__(self, bot):
        self.emoji = '🦉'
        self.brief = 'owner-only commands'
        self.bot: Ayane = bot

    async def cog_check(self, ctx: AyaneContext) -> bool:
        if await self.bot.is_owner(ctx.author):
            return True
        raise commands.NotOwner()

    @commands.group(name='dev', aliases=['d'], invoke_without_command=True, hidden=True, message_command=True)
    async def dev(self, ctx: AyaneContext, subcommand: str = None):
        if subcommand:
            return await ctx.send(f'Unknown subcommand `{subcommand}`', delete_after=5)

    @dev.command(name='restart', aliases=['reboot', 'r'], message_command=True)
    async def dev_restart(self, ctx: AyaneContext, *, service: str = 'ayane'):
        if LOCAL:
            return
        await ctx.send("Restarting the bot...")
        await ctx.bot.close()

    Status = typing.Literal['playing', 'streaming', 'listening', 'watching', 'competing']

    @dev.command(name='status', aliases=['ss'], message_command=True)
    async def dev_status(self, ctx: AyaneContext, status: Status, *, text: str):
        activity_types = {
            'playing': discord.ActivityType.playing,
            'streaming': discord.ActivityType.streaming,
            'listening': discord.ActivityType.listening,
            'watching': discord.ActivityType.watching,
            'competing': discord.ActivityType.competing,
        }
        extras = {}
        if status == 'streaming':
            extras['url'] = 'https://youtu.be/dQw4w9WgXcQ'
        await self.bot.change_presence(activity=discord.Activity(type=activity_types[status], name=text, **extras))
        await ctx.message.add_reaction('\N{WHITE HEAVY CHECK MARK}')

    @app_commands.command(name="role-assignment", description="You can add yourself roles to be pinged when there is "
                                                              "announcement about the topic they belong to.")
    @app_commands.guilds(800449566037114892)
    async def assign_roles(self, interaction, role: typing.Literal['Lib User', 'API User', 'Bot User']):
        reason = "role-assignment command"
        role = discord.utils.get(interaction.guild.roles, name=role)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role, reason=reason)
            return await interaction.response.send_message(f"I removed the **{role.name}** role from you.",
                                                           ephemeral=True)
        await interaction.user.add_roles(role, reason=reason)
        return await interaction.response.send_message(f"I added you the **{role.name}** role.",
                                                       ephemeral=True)
