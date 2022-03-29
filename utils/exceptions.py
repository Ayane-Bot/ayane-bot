import discord
import typing
from utils import constants
from discord.ext import commands


string_map = {
    discord.Member: "member",
    discord.User: "user",
    discord.Message: "message",
    discord.PartialMessage: "message",
    discord.TextChannel: "channel",
    discord.VoiceChannel: "voice channel",
    discord.StageChannel: "stage channel",
    discord.CategoryChannel: "category channel",
    discord.Invite: "invite",
    discord.Guild: "server",
    discord.Role: "role",
    discord.Game: "game",
    discord.Colour: "colour",
    discord.Emoji: "emoji",
    discord.PartialEmoji: "emoji",
    int: "whole number",
    float: "number",
    str: "string",
    bool: "boolean",
}


def join_literals(annotation, return_list: bool = False):
    if typing.get_origin(annotation) is typing.Literal:
        arguments = annotation.__args__
        if return_list is False:
            return '[' + '|'.join(arguments) + ']'
        else:
            return list(arguments)
    return None


def convert_union_annotations(param: inspect.Parameter):
    annotations = param.annotation
    args = typing.get_args(annotations)
    maybe_strings = [string_map.get(a, a) for a in args]
    for a in maybe_strings:
        if not isinstance(a, str):
            if argument := join_literals(a):
                maybe_strings.remove(a)
                maybe_strings.append(f"[{argument}]")
            else:
                maybe_strings.remove(a)
                maybe_strings.append('[unknown]')
    return ", ".join(maybe_strings[:-2] + [" or ".join(maybe_strings[-2:])])


def conv_n(tuple_acc):
    """A really bad code, but i'm lazy to fix"""
    returning = ""
    op_list_v = []
    op_list_n = list(tuple_acc)
    for i in range(len(op_list_n)):
        op_list_v.append(op_list_n[i].__name__.replace("Converter", ""))
    for i in range(len(op_list_v)):
        if i + 3 <= len(op_list_v):
            returning += f"{op_list_v[i].lower()}, "
        elif i + 2 <= len(op_list_v):
            returning += f"{op_list_v[i].lower()} or "
        else:
            returning += f"{op_list_v[i].lower()}"
    return returning

class NotAuthorized(Exception):
    """Exception raised when the user doesn't have the permission to click on the view menu"""

    def __init__(self, auth, message=None):
        self.auth = auth
        self.message = (
            f"Sorry, only **{self.auth.name if isinstance(self.auth, discord.User) or isinstance(self.auth, discord.Member) else auth}** "
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


class AlreadyMuted(Exception):
    pass


class NotMuted(Exception):
    pass


class IsStaffMember(Exception):
    pass


class IsAuthor(Exception):
    pass
