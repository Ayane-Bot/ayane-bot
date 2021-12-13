import os
from config import TOKEN
from discord.ext import commands
import logging

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(asctime)-15s] %(message)s')


class Ayane(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='ay!')
        self._load_cogs()

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
    bot.run(TOKEN)
