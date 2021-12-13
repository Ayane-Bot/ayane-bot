import os
import logging
import discord

from discord.ext import commands

from private.config import TOKEN, OWNER_IDS, DEFAULT_PREFIXES, LOCAL

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="[%(asctime)-15s] %(message)s")


class Ayane(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or(*DEFAULT_PREFIXES),
            strip_after_prefix=True,
            intents=discord.Intents.all(),
        )
        self.loop.create_task(self.set_bot_attrs())
        self._load_cogs()
        self.owner_ids = OWNER_IDS
        self.website = "https://ayane.live/"
        self.server_invite = "https://discord.gg/QNXC8yFfKg"
        self.colour = discord.Colour(value=0xA37FFF)

    async def set_bot_attrs(self):
        await self.wait_until_ready()
        self.invite = f"https://discord.com/oauth2/authorize?client_id={self.user.id}&scope=bot+applications.commands&permissions=173211516614&response_type=code&redirect_uri=https%3A%2F%2Fdiscord.gg%2Finvite%2FQNXC8yFfKg"

    async def on_ready(self):
        print("Logged in as", str(self.user))

    def _load_cogs(self):
        try:
            self.load_extension("jishaku")
        except Exception as e:
            logging.error(f"Failed to load jishaku", exc_info=e)
        for ext in os.listdir("./cogs"):
            if ext.endswith(".py"):
                try:
                    self.load_extension(f"cogs.{ext[:-3]}")
                except Exception as e:
                    logging.error(f"Failed to load extension {ext}.", exc_info=e)


if __name__ == "__main__":
    bot = Ayane()

    @bot.check
    async def running_locally(ctx):
        """If the bot is running locally, only allows the owner to use commands."""
        if LOCAL is False:
            return True
        return await bot.is_owner(ctx.author)

    bot.run(TOKEN)
