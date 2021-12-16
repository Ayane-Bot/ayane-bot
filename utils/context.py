import discord
from discord.ext import commands

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import Ayane
else:
    from discord.ext.commands import Bot as Ayane


class AyaneContext(commands.Context):
    bot: Ayane

    async def send(self, content=None, *, embed=None, **kwargs) -> discord.Message:
        if embed:
            if embed.colour is discord.Embed.Empty:
                embed.colour = self.bot.colour
                
        return await super().send(content=content, embed=embed, **kwargs)
