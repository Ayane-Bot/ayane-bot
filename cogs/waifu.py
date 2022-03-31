import os
import random
import time
import waifuim
import xxhash
import asyncio

import discord
from discord.ext import commands
from discord import app_commands

from utils.helpers import stop_if_nsfw
from utils.paginators import ImageMenu, FavMenu, ImageSource


class PictureConverter:
    def __init__(self, bot, file_string=None, file=None):
        self.file_string = file_string
        self.file = file
        if file_string:
            if "manage" in file_string or "preview" in file_string:
                self.maybe_id = os.path.splitext(file_string.split("image=")[-1])[0]
            else:
                self.maybe_id = os.path.splitext(file_string.split("/")[-1])[0]
        self.bot = bot
        self.is_url = None

    async def to_id(self):
        if self.file:
            return os.path.splitext(xxhash.xxh3_64_hexdigest(await self.file.read()))[0]
        filename = self.maybe_id
        try:
            rep = await self.bot.session.get(
                self.file_string, headers={"Referer": "https://pixiv.net"}
            )
            if "image" in rep.headers.get("content-type", ""):
                content = await rep.read()
                filename = xxhash.xxh3_64_hexdigest(content)
                self.is_url = True
        except:
            pass
        return filename


async def nsfw_tag_autocomplete(interaction, current):
    return [
        app_commands.Choice(name=tag.capitalize(), value=tag)
        for tag in interaction.client.waifu_im_tags['nsfw'] if current.lower() in tag.lower()
    ]


async def sfw_tag_autocomplete(interaction, current):
    return [
        app_commands.Choice(name=tag.capitalize(), value=tag)
        for tag in interaction.client.waifu_im_tags['sfw'] if current.lower() in tag.lower()
    ]


async def order_by_autocomplete(interaction, current):
    return [
        app_commands.Choice(name=type_.upper(), value=type_)
        for type_ in interaction.client.waifu_im_order_by if current.lower() in type_.lower()
    ]


async def setup(bot):
    await bot.add_cog(Waifu(bot))


class Waifu(commands.Cog):
    """The bot waifu API commands and some others."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = '<:ty:833356132075700254>'
        self.brief = 'The bot waifu API commands and some others.'
        self.bot.waifu_reason_exempted_users = {747737674952999024}

    async def not_empty(self, tag, is_nsfw):
        try:
            return bool(await self.bot.waifu_client.random(is_nsfw=is_nsfw, selected_tags=[tag]))
        except waifuim.APIException as e:
            if e.status == 429:
                await asyncio.sleep(0.25)
                return await self.not_empty(tag, is_nsfw)
            if e.status != 404:
                # We allow the tag even if it will error at least the user will get some traceback
                return True

    async def cog_load(self):
        try:
            while True:
                req = await self.bot.session.get('https://api.waifu.im/openapi.json')
                if req.status != 429:
                    resp = await req.json()
                    self.bot.waifu_im_order_by = resp['components']['schemas']['OrderByType']['enum']
                    break
                await asyncio.sleep(0.25)
        except:
            # If we can't fetch the enum values (wrong status code etc...) we still set up those two
            self.bot.waifu_im_order_by = ["UPLOADED_AT", "FAVOURITES"]
        raws = await self.bot.waifu_client.endpoints()
        try:
            self.bot.waifu_im_tags = dict(sfw=[t for t in raws['versatile'] if await self.not_empty(t, False)],
                                          nsfw=[t for t in raws['versatile'] + raws['nsfw'] if
                                                await self.not_empty(t, True)]
                                          )
        except:
            # If some unknown error happen we still set up some tags manually
            self.bot.waifu_im_tags = dict(sfw=['waifu'], nsfw=['waifu', 'ero'])

    @staticmethod
    async def waifu_launcher(
            interaction,
            is_nsfw=None,
            selected_tags=None,
            excluded_tags=None,
            is_gif=None,
            is_ephemeral=False,
            order_by=None,
            many=None,
            full=None,

    ):
        """Used to easily run most of the command for the Waifu cog"""
        fav_order = "FAVOURITES"
        await interaction.response.defer(ephemeral=is_ephemeral)
        start = time.perf_counter()
        try:
            r = await interaction.client.waifu_client.random(
                selected_tags=selected_tags,
                excluded_tags=excluded_tags,
                gif=is_gif,
                order_by=order_by,
                many=many,
                full=full,
                is_nsfw=is_nsfw,
            )
        except waifuim.APIException as error:
            if error.status == 404:
                return await interaction.followup.send(error.message)
            else:
                raise error
        end = time.perf_counter()
        request_time = round(end - start, 2)
        cleaned_category = selected_tags[0].capitalize()
        await ImageMenu(source=ImageSource(
            image_info=r,
            title=cleaned_category,
            per_page=1,
            user=interaction.user,
            request_time=None if order_by == fav_order else request_time,
        ),
            main_interaction=interaction,
            ephemeral=is_ephemeral,
        ).start()

    @app_commands.command(description="Look if an image exist on the api (the attachment field will be used if both "
                                      "are passed)")
    @app_commands.describe(
        file_name_or_url="A file name or an url to the file you want to look if it exist on the API.",
        attachment="A file that you want to look if it exist on the API. "
    )
    @app_commands.checks.cooldown(1, float(3), key=lambda i: (i.user.id,))
    async def pics(self,
                   interaction,
                   file_name_or_url: str = None,
                   attachment: discord.Attachment = None,
                   ephemeral: bool = False):
        """🔗 Send you the picture related to the ID or the url you provided, if there is matches. This will work
        only if the image is strictly the same. Passing an image that have been compressed or went through any
        process that might alter its content will not work **please note that using [Saucenao](
        https://saucenao.com)** to find the original **file** url is recommended. This command will display the image
        you want from the bot image API (for more information use `ayapi`). The ID is corresponding to the filename
        of the picture (without the extension), but you can still pass any url. `is_ephemeral` argument only work
        with slash commands. """
        if not attachment and not file_name_or_url:
            return await interaction.response.send_message("You must at least provide a file name a url or an "
                                                           "attachment")
        if attachment and attachment.content_type.split("/")[0] != "image":
            return await interaction.response.send_message("This command only support image attachment")
        if file_name_or_url:
            file_name_or_url = (
                file_name_or_url.strip("||||")
                    .strip("******")
                    .strip("****")
                    .strip("**")
                    .strip("<>")
            )
        converter = PictureConverter(self.bot, file_string=file_name_or_url, file=attachment)
        file_id = await converter.to_id()
        start = time.perf_counter()
        try:
            matches = await self.bot.waifu_client.info(images=[file_id])
        except waifuim.APIException as e:
            if e.status == 404:
                embed = discord.Embed(title="❌ File not found",
                                      description=f"Sorry i did not find any file that match your search :"
                                                  f"`{file_name_or_url}`. If you provided an url, please go check"
                                                  f"`/help {interaction.command.name}`. ")
                return await interaction.response.send_message(embed=embed)
            raise e
        image = matches[0]
        end = time.perf_counter()
        default = ["ero", "waifu"]
        filtered_tags = [t for t in image.tags if t.name not in default]
        tag = random.choice(filtered_tags) if len(image.tags) > 1 else image.tags[0]
        stop_if_nsfw(not interaction.channel.is_nsfw() and image.is_nsfw)

        return await ImageMenu(
            source=ImageSource(
                image_info=matches, user=interaction.user,
                title=tag.name.capitalize(),
                request_time=round(end - start, 2),
                per_page=1,
            ),
            ephemeral=ephemeral,
            main_interaction=interaction,
        ).start()

    @app_commands.command(name="favourite", description="Fetch a user favourite gallery from waifu.im API.")
    @app_commands.describe(is_nsfw="If provided set an nsfw filter depending on the value provided")
    async def favourite(self, interaction, is_nsfw: bool = None, ephemeral: bool = False):
        """🔗 Display your favorite pictures on the API site. https://waifu.im To add an image to your gallery you
        just need to clique on the heart when requesting an image using one of the bot API image command. the
        subcommands are the type of picture to return, either sfw or nsfw if nothing is provided no filter will be
        applied. The commands that use the bot [API](https://waifu.im/) are the nsfw commands and the `waifu`
        command. """
        stop_if_nsfw(not interaction.channel.is_nsfw() and (is_nsfw is None or is_nsfw))
        try:
            images = (await interaction.client.waifu_client.fav(user_id=interaction.user.id))["images"]
        except waifuim.APIException as e:
            if e.status == 404:
                return await interaction.response.send_message(
                    "You have no Gallery or it is empty. You can add some by using the bot API commands `/sfw waifu` "
                    "etc... "
                )
            else:
                raise e
        images = [waifuim.types.Image(i) for i in images]
        if is_nsfw is not None:
            images = list(filter(lambda image: image.is_nsfw == is_nsfw, images))
        title = interaction.user.name + " " + (
            "NSFW " if is_nsfw is True else "SFW " if is_nsfw is False else "") + "Gallery"
        await FavMenu(
            source=ImageSource(title=title, image_info=images, user=interaction.user, per_page=1),
            main_interaction=interaction,
            ephemeral=ephemeral,
        ).start()

    waifu = app_commands.Group(name="waifu", description="Get a random waifu picture from waifu.im API.")

    @waifu.command(name="sfw", description="Get a random safe picture from waifu.im API.")
    @app_commands.describe(tag="The image tag used to fetch images",
                           order_by="Sort image by a specific order",
                           gif="If you want only classic images or gifs",
                           many="To get a paginator of multiple files")
    @app_commands.autocomplete(tag=sfw_tag_autocomplete, order_by=order_by_autocomplete)
    async def sfw_(self, interaction, tag: str, order_by: str, gif: bool = None, many: bool = None):
        await self.waifu_launcher(
            interaction,
            is_nsfw=False,
            selected_tags=[tag],
            is_gif=gif,
            order_by=order_by,
            many=many,
        )

    @waifu.command(name="nsfw", description="Get a random lewd picture from waifu.im API.")
    @app_commands.describe(tag="The image tag used to fetch images",
                           order_by="Sort image by a specific order",
                           gif="If you want only classic images or gifs",
                           many="To get a paginator of multiple files")
    @app_commands.autocomplete(tag=nsfw_tag_autocomplete, order_by=order_by_autocomplete)
    async def nsfw_(self, interaction, tag: str, order_by: str, gif: bool = None, many: bool = None):
        await self.waifu_launcher(
            interaction,
            is_nsfw=True,
            selected_tags=[tag],
            is_gif=gif,
            order_by=order_by,
            many=many,
        )
