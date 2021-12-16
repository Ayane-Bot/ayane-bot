import os
import typing

import discord
from discord.ext import commands

from utils.defaults import AyaneCog, ayane_group
from utils.context import AyaneContext
from main import Ayane
from private.config import LOCAL


def setup(bot):
    bot.add_cog(Owner(bot))


class Owner(AyaneCog, emoji='🦉', brief='owner-only commands'):
    def __init__(self, bot):
        self.bot: Ayane = bot

    async def cog_check(self, ctx: AyaneContext) -> bool:
        if await self.bot.is_owner(ctx.author):
            return True
        raise commands.NotOwner()

    @ayane_group(name='dev', aliases=['d'],
                 invoke_without_command=True, hidden=True)
    async def dev(self, ctx: AyaneContext, subcommand: str = None):
        if subcommand:
            return await ctx.send(f'Unknown subcommand `{subcommand}`', delete_after=5)

    @dev.command(name='restart', aliases=['reboot', 'r'])
    async def dev_restart(self, ctx: AyaneContext, *, service: str = 'ayane'):
        if LOCAL:
            return
        await ctx.send(f'Restarting {service}...')
        os.system(f'sudo systemctl restart {service}')

    Status = typing.Literal['playing', 'streaming', 'listening', 'watching', 'competing']

    @dev.command(name='status', aliases=['ss'])
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
