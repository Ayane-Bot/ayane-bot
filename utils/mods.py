import datetime
from utils.exceptions import AlreadyMuted
import discord

class ModUtils:
    def __init__(self, reason_format: str = "You have been $action from **$guild**\n```Reason: $reason```"):
        self.reason_format = reason_format

    @staticmethod
    async def set_muted_role(self, guild):
        role = discord.utils.get(guild.roles, name="Muted")
        muted_permissions = guild.default_role.permissions
        muted_permissions.send_messages = False
        muted_permissions.connect = False
        if not role:
            role = await guild.create_role(
                name="Muted",
                colour=discord.Colour.darker_grey(),
                permissions=muted_permissions,
                reason="Muted role did not exist",
            )
        return role

    def format_sanction_reason(self, guild, reason, action):
        return self.reason_format.replace("$action", action).replace("$reason", reason).replace("$guild",guild.name)

    async def ban(self, guild, user, reason=None):
        await guild.ban(user, reason=reason)
        try:
            await user.send(self.format_sanction_reason(guild, reason, "Banned"))
        except discord.HTTPException:
            pass

    async def kick(self, member, reason=None ,delete_last_day=False, bypass_staff=False):
        if member.guild.get_member(member.id):
            await member.kick(reason=reason)
            try:
                await member.send(self.format_sanction_reason(member.guild, reason, "Kicked"))
            except discord.HTTPException:
                pass
            if delete_last_day:
                await self.purge(member.guild.text_channels,after=discord.utils.utcnow() - datetime.timedelta(days=1))

    async def mute(self, member, reason=None, delete_last_day=False):
        if member.guild.get_member(member.id):
            role = await self.set_muted_role(member.guild)
            if role in member.roles:
                raise AlreadyMuted
            await member.add_roles(role ,reason=reason)
            try:
                await member.send(self.format_sanction_reason(member.guild, reason, "Muted"))
            except discord.HTTPException:
                pass
            for category in member.guild.categories:
                await category.set_permissions(role, send_messages=False, connect=False)
            if delete_last_day:
                await self.purge(member.guild.text_channels,after=discord.utils.utcnow() - datetime.timedelta(days=1))

    async def unmute(self, member, reason=None, delete_last_day=False):
        if member.guild.get_member(member.id):
            role = await self.set_muted_role(member.guild)
            if role in member.roles:
                await member.remove_roles(role ,reason=reason)
            for category in member.guild.categories:
                await category.set_permissions(role, send_messages=False, connect=False)

    async def purge(self,channels, limit=None, after=None, user=None, original_message = None):
        if isinstance(channels, discord.abc.Messageable):
            channels=[channels]

        total = 0
        def check(m):
                if not user and original_message:
                    return m.id != original_message.id
                elif user and not original_message:
                    return m.author.id == user.id
                elif user and original_message:
                    return m.author.id == user.id and m.id != original_message.id
                return True
        for channel in channels:
            bulk = True
            if (user and user.id == channel.guild.me.id and not channel.permissions_for(
                    channel.guild.get_member(channel.guild.me.id)
            ).manage_messages):
                bulk = False
            if original_message and limit:
                limit += 1
            try:
                total += len(await channel.purge(limit=limit, check=check, after=after, bulk=bulk))
            except discord.HTTPException:
                pass
        return total




