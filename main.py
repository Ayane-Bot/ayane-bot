import os
import logging
import discord

from discord.ext import commands

from private.config import TOKEN, OWNER_IDS, DEFAULT_PREFIXES, LOCAL

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(asctime)-15s] %(message)s')


class Ayane(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=commands.when_mentioned_or(*DEFAULT_PREFIXES), strip_after_prefix=True)
        self._load_cogs()
        self.owner_ids = OWNER_IDS

    async def on_ready(self):
        print('Logged in as', str(self.user))

    def _load_cogs(self):
        try:
            self.load_extension('jishaku')
        except Exception as e:
            logging.error(f'Failed to load jishaku', exc_info=e)
        for ext in os.listdir('./cogs'):
            if ext.endswith('.py'):
                try:
                    self.load_extension(f'cogs.{ext[:-3]}')
                except Exception as e:
                    logging.error(f'Failed to load extension {ext}.', exc_info=e)


if __name__ == '__main__':
    bot = Ayane()

    @bot.check
    async def running_locally(ctx):
        """ If the bot is running locally, only allows the owner to use commands. """
        if LOCAL is False:
            return True
        return await bot.is_owner(ctx.author)

    bot.run(TOKEN)
