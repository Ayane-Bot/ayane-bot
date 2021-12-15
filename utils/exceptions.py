import discord
from discord.ext import commands


class NotAuthorized(Exception):
    """Exception raised when the user doesn't have the permission to click on the view menu"""

    def __init__(self, auth, message=None):
        self.auth = auth
        self.message = (
            f"Sorry, only **{self.auth.name if isinstance(self.auth, discord.User) or isinstance(self.auth, discord.Member) else auth}**"
            "can do this action. "
            if not message
            else message
        )
        super().__init__(self.message)


class LimitReached(Exception):
    def __init__(self, limit=None, user=None, counter=None):
        self.limit = limit
        self.user = user
        self.counter = counter


class UserBlacklisted(commands.CheckFailure):
    pass
