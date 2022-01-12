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

    def stop_if_nsfw(self, value):
        if isinstance(self.channel, (discord.Thread, discord.TextChannel)):
            is_nsfw = self.channel.is_nsfw()
        else:
            is_nsfw = False
        if value and not is_nsfw:
            raise commands.NSFWChannelRequired(self.channel)