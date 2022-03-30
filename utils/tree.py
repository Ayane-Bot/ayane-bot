import math
import humanize

import discord
from discord import app_commands

from utils import exceptions


class AyaneCommandTree(app_commands.CommandTree):

    async def interaction_check(self, interaction) -> bool:
        for check in interaction.client.default_checks:
            if await check(interaction) is False:
                return False
        return True
