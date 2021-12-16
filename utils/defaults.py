from typing import Callable, Union, Concatenate, Any, Type

from discord.utils import MISSING  # noqa
from discord.ext.commands import Cog, command as cmd, Command, group as cmd_g, Group
from discord.ext.commands.core import ContextT, P, Coro, T, CogT, CommandT, GroupT  # noqa

from private.config import LOCAL


class AyaneCog(Cog):
    def __init_subclass__(cls, **kwargs):
        cls.emoji = kwargs.pop('emoji', None)
        cls.brief = kwargs.pop('brief', None)
        cls.icon = kwargs.pop('icon', None)
        super().__init_subclass__(**kwargs)


def ayane_command(name: str = MISSING, cls: Type[CommandT] = MISSING, **attrs) -> Callable[
    [
        Union[
            Callable[[Concatenate[ContextT, P]], Coro[Any]],
            Callable[[Concatenate[CogT, ContextT, P]], Coro[T]],
        ]
    ],
    Union[Command[CogT, P, T], CommandT],
]:
    """ The `@command` decorator but with some dumb stuff for some dumb fork... """
    try:
        slash = attrs['slash_command']
        if slash is True and LOCAL is True:
            raise RuntimeError('Slash commands are not allowed in local mode.')
    except KeyError:
        attrs['slash_command'] = not LOCAL
    try:
        attrs['message_command']
    except KeyError:
        attrs['message_command'] = LOCAL
    return cmd(name=name, cls=cls, **attrs)


def ayane_group(
    name: str = MISSING,
    cls: Type[GroupT] = MISSING,
    **attrs: Any,
) -> Callable[
    [
        Union[
            Callable[[Concatenate[ContextT, P]], Coro[Any]],
            Callable[[Concatenate[CogT, ContextT, P]], Coro[T]],
        ]
    ],
    Union[Group[CogT, P, T], GroupT],
]:
    """ The `@group` decorator but with some dumb stuff for some dumb fork... """
    try:
        slash = attrs['slash_command']
        if slash is True and LOCAL is True:
            raise RuntimeError('Slash commands are not allowed in local mode.')
    except KeyError:
        attrs['slash_command'] = not LOCAL
    try:
        attrs['message_command']
    except KeyError:
        attrs['message_command'] = LOCAL

    return cmd_g(name=name, cls=cls, **attrs)  # type: ignore
