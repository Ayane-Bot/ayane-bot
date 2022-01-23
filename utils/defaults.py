from typing import Callable, Union, Any, Type, Generic, TypeVar

import discord
from discord.ext.commands import Cog, command as cmd, Command, group as cmd_g, Group, DisabledCommand, CheckFailure
from discord.ext.commands._types import Coro  # noqa
from discord.ext.commands.core import ContextT, T, CogT, CommandT, GroupT  # noqa
from discord.utils import MISSING  # noqa
from typing_extensions import Concatenate, ParamSpec

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

    async def can_run(self, ctx) -> bool:
        """|coro|
        Checks if the command can be executed by checking all the predicates
        inside the :attr:`~Command.checks` attribute. This also checks whether the
        command is disabled.
        .. versionchanged:: 1.3
            Checks whether the command is disabled or not
        Parameters
        -----------
        ctx: :class:`.Context`
            The ctx of the command currently being invoked.
        Raises
        -------
        :class:`CommandError`
            Any command error that was raised during a check call will be propagated
            by this function.
        Returns
        --------
        :class:`bool`
            A boolean indicating if the command can be invoked.
        """
        guild_id = ctx.guild.id if ctx.guild else None
        if not self.enabled:
            raise DisabledCommand(f"{self.name} command is disabled")

        if ctx.interaction is None and (
            (
                self.message_command is False
                and guild_id not in ctx.bot.verified_message_command_guilds
                and ctx.author.id not in ctx.bot.verified_message_command_user_ids
            )
            or (self.message_command is None and not ctx.bot.message_commands)
        ):
            raise DisabledCommand(f"{self.name} command cannot be run as a message command. "
                                  f"Please use `/{self.name}` instead.")

        if ctx.interaction is not None and (
            (
                self.slash_command is False
                and guild_id not in ctx.bot.verified_slash_command_guilds
                and ctx.author.id not in ctx.bot.verified_slash_command_user_ids
            )
            or (self.slash_command is None and not ctx.bot.slash_commands)
        ):
            raise DisabledCommand(f"{self.name} command cannot be run as a slash command")

        original = ctx.command
        ctx.command = self

        try:
            if not await ctx.bot.can_run(ctx):
                raise CheckFailure(
                    f"The global check functions for command {self.qualified_name} failed."
                )

            cog = self.cog
            if cog is not None:
                local_check = Cog._get_overridden_method(cog.cog_check)
                if local_check is not None:
                    ret = await discord.utils.maybe_coroutine(local_check, ctx)
                    if not ret:
                        return False

            predicates = self.checks
            if not predicates:
                # since we have no checks, then we just return True.
                return True

            return await discord.utils.async_all(predicate(ctx) for predicate in predicates)  # type: ignore
        finally:
            ctx.command = original


class AyaneGroup(Group, AyaneCommand[CogT, D, T]):
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
