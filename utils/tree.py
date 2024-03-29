import math
import humanize

import discord
from discord.ext.commands import NotOwner as CommandNotOwner
from discord import app_commands

from utils import exceptions


class AyaneCommandTree(app_commands.CommandTree):
    async def call(self, interaction):
        await super().call(interaction)
        interaction.client.dispatch("app_command", interaction)

    async def on_error(
            self,
            interaction,
            error,
    ) -> None:
        """Handles command exceptions and logs unhandled ones to the support guild."""

        embed = discord.Embed(colour=interaction.client.colour)
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original

        if isinstance(error, app_commands.errors.CommandNotFound):
            embed.title = "🛑 Command Not Found"
            embed.description = "Sorry this command does not exist anymore."
            await interaction.client.send_interaction_error_message(interaction, embed=embed)
        elif isinstance(error, app_commands.CheckFailure):
            if isinstance(error, app_commands.BotMissingPermissions):
                missing = [(e.replace('_', ' ').replace('guild', 'server')).title() for e in error.missing_permissions]
                perms_formatted = "**, **".join(missing[:-2] + ["** and **".join(missing[-2:])])
                _message = f"I need the **{perms_formatted}** permission(s) to run this command."
                embed.title = "❌ Bot missing permissions"
                embed.description = _message
                await interaction.client.send_interaction_error_message(interaction, embed=embed)

            elif isinstance(error, app_commands.CommandOnCooldown):
                _message = f"This command is on cooldown, please retry in {humanize.time.precisedelta(math.ceil(error.retry_after))}. "
                embed.title = "🛑 Command on cooldown"
                embed.description = _message
                await interaction.client.send_interaction_error_message(interaction, embed=embed)

            elif isinstance(error, app_commands.MissingPermissions):
                missing = [(e.replace('_', ' ').replace('guild', 'server')).title() for e in error.missing_permissions]
                perms_formatted = "**, **".join(missing[:-2] + ["** and **".join(missing[-2:])])
                _message = f"You need the **{perms_formatted}** permission(s) to use this command."
                embed.title = "🛑 Missing permissions"
                embed.description = _message
                await interaction.client.send_interaction_error_message(interaction, embed=embed)

            elif isinstance(error, app_commands.MissingRole):
                missing = error.missing_role
                _message = f"You need the **{missing}** role to use this command."
                embed.title = "🛑 Missing role"
                embed.description = _message
                await interaction.client.send_interaction_error_message(interaction, embed=embed)

            elif isinstance(error, app_commands.NoPrivateMessage):
                return

            elif isinstance(error, exceptions.NSFWChannelRequired):
                _message = "Sorry, I cannot display **NSFW** content in this channel."
                embed.title = "🛑 NSFW channel required"
                embed.description = _message
                await interaction.client.send_interaction_error_message(interaction, embed=embed)

            elif isinstance(error, (exceptions.NotOwner, CommandNotOwner)):
                _message = f"Sorry **{interaction.user}**, but this commmand is an owner-only command and you arent one " \
                           f"of my loved developers <:ty:833356132075700254>."
                embed.title = "🛑 Owner-only"
                embed.description = _message
                await interaction.client.send_interaction_error_message(interaction, embed=embed)

            elif isinstance(error, exceptions.UserBlacklisted):
                embed.title = "🛑 Blacklisted"
                embed.description = str(error)
                await interaction.client.send_interaction_error_message(interaction, embed=embed)
            else:
                embed.title = "🛑 Check Failure",
                embed.description = "You or the bot cannot run this command."
                await interaction.client.send_interaction_error_message(interaction, embed=embed)
        elif isinstance(error, discord.Forbidden):
            embed.title = "🛑 Forbidden",
            embed.description = "Sorry I dont have enough permissions to do this."
            await interaction.client.send_interaction_error_message(interaction, embed=embed)
        elif isinstance(error, app_commands.TransformerError):
            embed.title = "🛑 Bad Argument"
            embed.description = str(error)
            await interaction.client.send_interaction_error_message(interaction, embed=embed)
        else:
            await interaction.client.send_unexpected_error(interaction, error)

    async def interaction_check(self, interaction) -> bool:
        for check in interaction.client.default_checks:
            if await check(interaction) is False:
                return False
        return True
