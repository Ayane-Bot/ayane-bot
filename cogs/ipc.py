import discord

from discord.ext import commands
from aiohttp import web


class IPC(commands.Cog):
    """The bot IPC server"""

    def __init__(self, bot):
        self._webserver = None
        self.bot = bot
        self.bot.server = web.Application()

    async def cog_load(self):
        self.bot.loop.create_task(self.run())

    async def user_info_handler(self, request):
        dict_ = {}
        uid = int(request.rel_url.query.get("id"))
        try:
            user = await self.bot.fetch_user(uid)
        except discord.errors.NotFound:
            raise web.HTTPNotFound
        return web.json_response(
            dict(id=user.id, name=user.name, full_name=str(user), avatar_url=user.display_avatar.url))

    async def run(self):
        await self.bot.wait_until_ready()
        self.bot.server.router.add_get("/userinfo/", self.user_info_handler)
        runner = web.AppRunner(self.bot.server)
        await runner.setup()
        self._webserver = web.TCPSite(runner, "127.0.0.1", "8033")
        await self._webserver.start()
        print("Starting IPC server")


async def setup(bot):
    await bot.add_cog(IPC(bot))
