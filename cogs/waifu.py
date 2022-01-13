import os
import random
import time
import waifuim
import xxhash

import discord
from discord.ext import commands

from utils import defaults
from utils.exceptions import APIServerError
from utils.paginators import ImageMenu, FavMenu, ImageSource, ViewMenuLauncher


class PictureConverter:
    def __init__(self, u_input, bot):
        self.u_input = u_input
        self.maybe_id = os.path.splitext(u_input.split("/")[-1])[0]
        self.bot = bot
        self.is_url = None

    async def url_to_id(self):
        filename = self.maybe_id
        try:
            rep = await self.bot.session.get(
                self.u_input, headers={"Referer": "https://pixiv.net"}
            )
            content = await rep.read()
            filename = xxhash.xxh3_64_hexdigest(content)
            self.is_url = True
        except Exception:
            pass

        return filename

    
def setup(bot):
    bot.add_cog(Waifu(bot))
    

class Waifu(defaults.AyaneCog, emoji='<:ty:833356132075700254>', brief='The bot waifu API commands and some others.'):
    """The bot waifu API commands and some others."""
    def __init__(self, bot):
        self.bot = bot
        self.bot.waifu_reason_exempted_users = {747737674952999024}
        if not self.bot.loop.is_running():
            self.bot.loop.run_until_complete(self.helpdescription())
        else:
            self.bot.loop.create_task(self.helpdescription())

    async def helpdescription(self):
        rep = await self.bot.waifuclient.endpoints(full=True)
        for c in self.walk_commands():
            for t in rep["sfw"]:
                if t["name"] == str(c.help.split(" ")[-1]) and t["is_nsfw"] == bool(
                        int(c.help.split(" ")[0])
                ):
                    if not c.parent:
                        c.description = random.choice(
                            ["True", "1", "0", "False", "false", "true"]
                        )
                    c.help = f"""{t['description']}
{'`is_gif` argument only accept boolean, 1, 0, true, false etc..' if not c.parent else ''}"""
            for t in rep["nsfw"]:
                if t["name"] == str(c.help.split(" ")[-1]) and t["is_nsfw"] == bool(
                        int(c.help.split(" ")[0])
                ):
                    if not c.parent:
                        c.description = random.choice(
                            ["True", "1", "0", "False", "false", "true"]
                        )
                    c.help = f"""⚠ NSFW. {t['description']}
{'`is_gif` argument only accept boolean, 1, 0, true, false etc..' if not c.parent else ''}"""
                    setattr(c, "nsfw", True)

    @staticmethod
    async def waifu_launcher(
            ctx,
            typ,
            category,
            is_gif=None,
            is_ephemeral=False,
            top=None,
            many=False
    ):
        """Used to easily run most of the command for the Waifu cog"""
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=is_ephemeral)
        start = time.perf_counter()
        if typ is None or category is None:
            r = await getattr(ctx.bot.waifuclient, "random")(
                gif=is_gif if not top else None, raw=True, top=top, many=many
            )
        else:
            r = await getattr(ctx.bot.waifuclient, typ)(
                category, gif=is_gif if not top else None, raw=True, top=top, many=many
            )
        end = time.perf_counter()
        request_time = round(end - start, 2)
        cleaned_category = "" if typ is None or category is None else category.capitalize()
        category = "Top " + cleaned_category if top else cleaned_category
        category = (
            f"{ctx.invoked_with.capitalize()} best {cleaned_category}"
            if ctx.invoked_with.lower() in ctx.command.aliases
            else category
        )
        await ViewMenuLauncher(
            viewmenu=ImageMenu(
                source=ImageSource(
                    r["images"],
                    title=category,
                    per_page=1,
                    user=ctx.author,
                    request_time=None if top else request_time,
                ),
                ctx=ctx,
                ephemeral=is_ephemeral,
            )
        ).start()

    @defaults.ayane_command()
    async def waifu(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """0 waifu"""
        category = "waifu"
        await self.waifu_launcher(
            ctx, "sfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command(aliases=["proguy", "progirl"])
    async def maid(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """0 maid"""
        category = "maid"
        await self.waifu_launcher(
            ctx, "sfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command(description="c19af2c9a399d0a3")
    @commands.cooldown(1, float(3), commands.BucketType.user)
    async def pics(
            self,
            ctx,
            file_id_or_url,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """🔗 Send you the picture related to the ID or the url you provided, if there is matches.
        This will work only if the image is strictly the same.
        Passing an image that have been compressed or went trough any process that might alter its content will not work
        **please note that using [Saucenao](https://saucenao.com)** to find the original **file** url is recommended.
        This command will display the image you want from the bot's image API (for more informations use `ayapi`).
        The ID is corresponding to the filename of the picture (without the extension), but you can still pass any url.
        `is_ephemeral` argument only work with slash commands."""
        file_id_or_url = (
            file_id_or_url.strip("||||")
                .strip("******")
                .strip("****")
                .strip("**")
                .strip("<>")
        )
        converter = PictureConverter(file_id_or_url, self.bot)
        file_id = await converter.url_to_id()
        start = time.perf_counter()
        try:
            matches = await self.bot.waifuclient.info(images=[file_id])
        except waifuim.APIException as e:
            if e.status == 404:
                embed = discord.Embed(title="❌ File not found",
                                      description=f"Sorry i did not find any file that match your search :"
                                                  f"`{file_id_or_url}`. If you provided an url, please go check"
                                                  f"`{ctx.clean_prefix}help {ctx.command.name}`. ")
                return await ctx.send(embed=embed)
            raise e
        end = time.perf_counter()
        default = ["ero", "waifu"]
        tags = matches["images"][0]["tags"]
        tag = (
            random.choice([t for t in tags if not t["name"] in default])
            if len(tags) > 1
            else tags[0]
        )

        if tag["is_nsfw"]:
            if not ctx.channel.is_nsfw():
                raise commands.NSFWChannelRequired(ctx.channel)

        return await ViewMenuLauncher(
            viewmenu=ImageMenu(
                source=ImageSource(
                    matches["images"],
                    user=ctx.author,
                    title=tag["name"].capitalize(),
                    request_time=round(end - start, 2),
                    per_page=1,
                ),
                ctx=ctx,
                ephemeral=is_ephemeral,
            )
        ).start()

    @defaults.ayane_group(
        aliases=["fav", "favorite", "gallery", "gallerys", "fv"],
        description="false",
        invoke_without_command=True,
    )
    async def favourite(self, ctx):
        """🔗 Display your favorite pictures on the API site. https://waifu.im
        To add an image to your gallery you just need to clique on the heart when requesting an image using one of the bot API image command.
        the subcommands are the type of picture to return, either sfw or nsfw if nothing is provided no filter will be applied.
        The commands that use the bot [API](https://waifu.im/) are the nsfw commands and the `waifu` command."""
        stre = f"I did not find any subcommand named `{ctx.invoked_subcommand}`"
        return await ctx.send(
            f"""Sorry you did not provide a valid subcommand, please choose one of the following : {' '.join([f"`{c.name}`" for c in ctx.command.walk_commands()])}."""
        )

    @favourite.ayane_command()
    @commands.is_nsfw()
    async def overall(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """🔗 Disable all filters."""
        try:
            images = await self.bot.waifuclient.fav(user_id=ctx.author.id)
        except waifuim.APIException as e:
            if e.status == 404:
                return await ctx.send(
                    "You have no Gallery or it is empty. You can add some by using the bot API commands, such as `top` `waifu` etc..."
                )
            else:
                raise e
        liste_im = images["images"]

        if not liste_im:
            return await ctx.send(
                "You have no Gallery or it is empty. You can add some by using the bot API commands, such as `top` `waifu` etc..."
            )
        return await ViewMenuLauncher(
            viewmenu=FavMenu(
                source=ImageSource(
                    liste_im,
                    title=f"{ctx.author.name}'s Gallery",
                    per_page=1,
                    user=ctx.author,
                ),
                ctx=ctx,
                ephemeral=is_ephemeral,
            )
        ).start()

    @favourite.ayane_command()
    async def sfw(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """🔗 Activate sfw filter"""
        try:
            images = await self.bot.waifuclient.fav(user_id=ctx.author.id)
        except waifuim.APIException as e:
            if e.status == 404:
                return await ctx.send(
                    "You have no Gallery or it is empty. You can add some by using the bot API commands, such as `top` `waifu` etc..."
                )
            else:
                raise e
        liste_im = [im for im in images["images"] if not im["tags"][0]["is_nsfw"]]
        if not liste_im:
            return await ctx.send(
                "Sorry I cannot display any picture in your gallery because they do not match the current filter."
            )
        return await ViewMenuLauncher(
            viewmenu=FavMenu(
                source=ImageSource(
                    liste_im,
                    title=f"{ctx.author.name}'s SFW Gallery",
                    per_page=1,
                    user=ctx.author,
                ),
                ctx=ctx,
                ephemeral=is_ephemeral,
            )
        ).start()

    @favourite.ayane_command()
    @commands.is_nsfw()
    async def nsfw(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """⚠🔗 NSFW. Activate nsfw filter
        sfw filter will be force applied if requesting in an non nsfw channel (only if you are not using a slash-command, otherwise is_ephemeral will be activated instead)."""
        try:
            images = await self.bot.waifuclient.fav(user_id=ctx.author.id)
        except waifuim.APIException as e:
            if e.status == 404:
                return await ctx.send(
                    "You have no Gallery or it is empty. You can add some by using the bot API commands, such as `top` `waifu` etc..."
                )
            else:
                raise e
        liste_im = [im for im in images["images"] if im["tags"][0]["is_nsfw"]]
        if not liste_im:
            return await ctx.send(
                "Sorry I cannot display any picture in your gallery because they do not match the current filter."
            )
        return await ViewMenuLauncher(
            viewmenu=FavMenu(
                source=ImageSource(
                    liste_im,
                    title=f"{ctx.author.name}'s NSFW Gallery",
                    per_page=1,
                    user=ctx.author,
                ),
                ctx=ctx,
                ephemeral=is_ephemeral,
            )
        ).start()

    @defaults.ayane_group(aliases=["best", "trending"], invoke_without_command=True)
    async def top(self, ctx):
        """🔗 Display the top images of a specific tag on the API site.
        to see the list of subcommands (aka tags you can use) see `help top`
        Little tips, the default tag for an sfw image is `waifu` and the default one for an nsfw image is `ero`"""
        return await ctx.send(
            f"""Sorry you did not provide a valid subcommand, please choose one of the following : {' '.join([f"`{c.name}`" for c in ctx.command.walk_commands()])}."""
        )

    @top.ayane_command(name="overall")
    @commands.is_nsfw()
    async def overall_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """The top Images overall.
        You can report the picture with the report button (if it contains lolis or if the image is not related to the command title for example).
        Abusing this feature will get you blacklisted..
        `is_ephemeral` argument only work with slash commands."""
        await self.waifu_launcher(
            ctx, None, None, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="waifu")
    async def waifu_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """0 waifu"""
        category = "waifu"
        await self.waifu_launcher(
            ctx, "sfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="maid")
    async def maid_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """0 maid"""
        category = "maid"
        await self.waifu_launcher(
            ctx, "sfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="ero")
    @commands.is_nsfw()
    async def ero_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 ero"""
        category = "ero"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="hentai")
    @commands.is_nsfw()
    async def hentai_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 hentai"""
        category = "hentai"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="paizuri")
    @commands.is_nsfw()
    async def paizuri_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 paizuri"""
        category = "paizuri"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="ecchi")
    @commands.is_nsfw()
    async def ecchi_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 ecchi"""
        category = "ecchi"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(aliases=["boobs", "tits"], name="oppai")
    @commands.is_nsfw()
    async def oppai_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 oppai"""
        category = "oppai"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="hmaid")
    @commands.is_nsfw()
    async def hmaid_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 maid"""
        category = "maid"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="uniform")
    @commands.is_nsfw()
    async def uniform_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 uniform"""
        category = "uniform"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="ass")
    @commands.is_nsfw()
    async def ass_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 ass"""
        category = "ass"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="milf")
    @commands.is_nsfw()
    async def milf_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 milf"""
        category = "milf"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="selfies", aliases=["selfie"])
    @commands.is_nsfw()
    async def selfies_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 selfies"""
        category = "selfies"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    @top.ayane_command(name="oral")
    @commands.is_nsfw()
    async def oral_(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
    ):
        """1 oral"""
        category = "oral"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_ephemeral=is_ephemeral, top=True, many=True
        )

    """Normal commands"""

    @defaults.ayane_command(aliases=["dank"])
    @commands.is_nsfw()
    async def ero(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 ero"""
        category = "ero"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command()
    @commands.is_nsfw()
    async def hentai(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 hentai"""
        category = "hentai"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command()
    @commands.is_nsfw()
    async def paizuri(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 paizuri"""
        category = "paizuri"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command()
    @commands.is_nsfw()
    async def ecchi(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 ecchi"""
        category = "ecchi"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command(
        aliases=["boobs", "tits", "perez"],
    )
    @commands.is_nsfw()
    async def oppai(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 oppai"""
        category = "oppai"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command()
    @commands.is_nsfw()
    async def hmaid(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 maid"""
        category = "maid"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command()
    @commands.is_nsfw()
    async def uniform(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 uniform"""
        category = "uniform"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command()
    @commands.is_nsfw()
    async def ass(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 ass"""
        category = "ass"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command()
    @commands.is_nsfw()
    async def milf(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 milf"""
        category = "milf"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command(aliases=["selfie"])
    @commands.is_nsfw()
    async def selfies(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 selfies"""
        category = "selfies"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command()
    @commands.is_nsfw()
    async def oral(
            self,
            ctx,
            is_ephemeral: bool = commands.Option(
                default=False,
                description="Wether or not you want the message to be ephemeral",
            ),
            many: bool = commands.Option(
                default=None, description="If provided display many images."
            ),
            is_gif: bool = commands.Option(
                default=None,
                description="if provided, force or prevent the API to return .gif files.",
            ),
    ):
        """1 oral"""
        category = "oral"
        await self.waifu_launcher(
            ctx, "nsfw", category, is_gif=is_gif, is_ephemeral=is_ephemeral, many=many
        )

    @defaults.ayane_command(aliases=["stella"])
    async def femboy(self, ctx):
        """Get a femboy image from api.shiro.gg"""
        start = time.perf_counter()
        rq = await self.bot.session.get("https://api.shiro.gg/images/trap")
        end = time.perf_counter()
        if rq.status != 200:
            raise APIServerError(f"Shiro.gg status code was {rq.status}")
        rq = await rq.json()
        embed = discord.Embed(colour=discord.Colour.random(), url=rq["url"])
        embed.set_author(name="Femboy", url=rq["url"])
        embed.set_footer(text=f"shiro.gg | {round(end - start, 2)}")
        embed.set_image(url=rq["url"])
        await ctx.send(embed=embed)
