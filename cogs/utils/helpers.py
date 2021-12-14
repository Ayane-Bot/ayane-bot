from collections import Counter

import discord

from cogs.utils.context import AyaneContext
from private.config import LOCAL


async def do_removal(ctx: AyaneContext, limit: int, predicate, *, before=None, after=None, bulk: bool = True) -> None:
    """
    A helper method to remove up to `limit` messages that satisfy
    `predicate` in between `before` and `after` in `channel`. If
    `before` or `after` is None, it is ignored. If `bulk` is True, the
    messages are removed via bulk delete, else, it will remove them
    one by one.
    Source: https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/mod.py#L1202-L1234

    :param ctx: The context of the command.
    :param limit: The maximum amount of messages to remove.
    :param predicate: The predicate that checks if a message should be removed.
    :param before: The discord id before which all messages are removed.
    :param after: The discord id after which all messages are removed.
    :param bulk: Whether to remove messages via bulk delete.
    :return: None
    """

    if limit > 2000:
        return await ctx.send(f'Too many messages to search given ({limit}/2000)')

    async with ctx.typing():
        if before is None:
            before = ctx.message
        else:
            before = discord.Object(id=before)

        if after is not None:
            after = discord.Object(id=after)

        try:
            deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate, bulk=bulk)
        except discord.Forbidden:
            return await ctx.send('I do not have permissions to delete messages.')
        except discord.HTTPException as e:
            return await ctx.send(f'Error: {e} (try a smaller search?)')

        spammers = Counter(m.author.display_name for m in deleted)
        deleted = len(deleted)
        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'**{name}**: {count}' for name, count in spammers)

        to_send = '\n'.join(messages)

        if len(to_send) > 2000:
            await ctx.send(f'Successfully removed {deleted} messages.', delete_after=10)
        else:
            await ctx.send(to_send, delete_after=10)


class PersistentExceptionView(discord.ui.View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.bot.is_owner(interaction.user) and LOCAL is False

    @discord.ui.button(emoji='🗑', label='Mark as resolved', custom_id='persistant_exception_view_mark_as_resolved')
    async def resolve(self, _, interaction: discord.Interaction):
        message = interaction.message
        error = '```py\n' + '\n'.join(message.content.split('\n')[7:])
        await message.edit(content=f"{error}```fix\n✅ Marked as fixed by {interaction.user}.```", view=None)
