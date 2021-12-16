from typing import Callable, Union, Any, Type, TYPE_CHECKING, Generic, TypeVar
from typing_extensions import Concatenate, ParamSpec

from discord.utils import MISSING  # noqa
from discord.ext.commands import Cog, command as cmd, Command, group as cmd_g, Group
from discord.ext.commands.core import ContextT, T, CogT, CommandT, GroupT  # noqa
from discord.ext.commands._types import Coro  # noqa

from private.config import LOCAL, PREVENT_LOCAL_COMMANDS

P = ParamSpec("P")
D = TypeVar("D")


class AyaneCog(Cog):
    def __init_subclass__(cls, **kwargs):
        cls.emoji = kwargs.pop('emoji', None)
        cls.brief = kwargs.pop('brief', None)
        cls.icon = kwargs.pop('icon', None)
        super().__init_subclass__(**kwargs)


class AyaneCommand(Command, Generic[CogT, D, T]):
    def __init__(self, *args, **kwargs):
        self.icon = kwargs.pop('icon', None)
        super().__init__(*args, **kwargs)


class AyaneGroup(Group, Command[CogT, D, T]):
    def __init__(self, *args, **kwargs):
        self.icon = kwargs.pop('icon', None)
        super().__init__(*args, **kwargs)

    def ayane_command(
            self,
            name: str = MISSING,
            cls: Type[Command[CogT, P, T]] = MISSING,
            *args: Any,
            **kwargs: Any,
    ) -> Callable[
        [
            Union[
                Callable[[Concatenate[CogT, ContextT, P]], Coro[T]],
                Callable[[Concatenate[ContextT, P]], Coro[T]],
            ]
        ],
        AyaneCommand[CogT, P, T],
    ]:
        try:
            slash = kwargs['slash_command']
            if slash is True and LOCAL is True and PREVENT_LOCAL_COMMANDS is True:
                raise RuntimeError('Slash commands are not allowed in local mode.')
        except KeyError:
            kwargs['slash_command'] = not LOCAL
        try:
            kwargs['message_command']
        except KeyError:
            kwargs['message_command'] = LOCAL

        if cls is MISSING:
            cls = AyaneCommand

        return super().command(name, cls, *args, **kwargs)

    def command(
        self,
        name: str = MISSING,
        cls: Type[AyaneCommand[CogT, P, T]] = MISSING,
        *args: Any,
        **kwargs: Any,
    ):
        raise RuntimeError('Please use the method `ayane_command` instead.')


def ayane_command(name: str = MISSING, cls: Type[CommandT] = MISSING, **attrs) -> Callable[
    [
        Union[
            Callable[[Concatenate[ContextT, P]], Coro[Any]],
            Callable[[Concatenate[CogT, ContextT, P]], Coro[T]],
        ]
    ],
    Union[AyaneCommand[CogT, P, T], CommandT],
]:
    """ The `@command` decorator but with some dumb stuff for some dumb fork... """
    try:
        slash = attrs['slash_command']
        if slash is True and LOCAL is True and PREVENT_LOCAL_COMMANDS is True:
            raise RuntimeError('Slash commands are not allowed in local mode.')
    except KeyError:
        attrs['slash_command'] = not LOCAL
    try:
        attrs['message_command']
    except KeyError:
        attrs['message_command'] = LOCAL

    if cls is MISSING:
        cls = AyaneCommand

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
    Union[AyaneGroup[CogT, P, T], GroupT],
]:
    """ The `@group` decorator but with some dumb stuff for some dumb fork... """
    try:
        slash = attrs['slash_command']
        if slash is True and LOCAL is True and PREVENT_LOCAL_COMMANDS is True:
            raise RuntimeError('Slash commands are not allowed in local mode.')
    except KeyError:
        attrs['slash_command'] = not LOCAL
    try:
        attrs['message_command']
    except KeyError:
        attrs['message_command'] = LOCAL

    if cls is MISSING:
        cls = AyaneGroup

    return cmd_g(name=name, cls=cls, **attrs)  # type: ignore
