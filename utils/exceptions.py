import discord
from utils import constants
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


class UserLocked(commands.UserInputError):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class UserBlacklisted(commands.CheckFailure):
    def __init__(self, user, message=None, reason="No reason provided"):
        self.user = user
        self.reason = reason
        self.message = message or f"Sorry **{user}**, you have been permanently blacklisted" \
                                  "by a moderator from the bot support server. If you think it's an error please" \
                                  f"join the [support server]({constants.server_invite}).\n```Reason : {self.reason}```"
        super().__init__(self.message)


class APIServerError(commands.CommandError):
    pass
