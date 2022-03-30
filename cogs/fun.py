import discord
from discord.ext import commands
from discord import app_commands

from main import Ayane
from utils.paginators import BaseSource, ViewMenu
from utils.helpers import stop_if_nsfw

import kadal
# fork at https://github.com/Bucolo/Kadal/
import re
from dateutil.parser import parse


async def setup(bot):
    await bot.add_cog(Fun(bot))


anilisticon = "https://www.gitbook.com/cdn-cgi/image/" \
              "width=40,height=40,fit=contain,dpr=1," \
              "format=auto/https%3A%2F%2Fanilist.gitbook.io%2F~%2Ffiles%2Fv0%2Fb%2Fgitbook-28427.appspot.com" \
              "%2Fo%2Fspaces%252F-LHizcWWtVphqU90YAXO%252Favatar.png" \
              "%3Fgeneration%3D1531944291782256%26alt%3Dmedia"


class Fun(commands.Cog):
    def __init__(self, bot):
        self.emoji = '🎢'
        self.brief = 'Some fun commands'
        self.bot: Ayane = bot
        self.kadalclient = kadal.Client(session=self.bot.session)

    @staticmethod
    def format_error_message(search, safe_search=False):
        error_message = f"Sorry I did not find anything that match your search `{search}`\n\n"
        if safe_search:
            error_message += "*The safe search is active, you may want to try in an nsfw-channel to disable it.*"
        return error_message

    @staticmethod
    def format_anilist_embeds(media, safe_search=False, index=0, total=0):
        footer_text = "Safe Search • " if safe_search else ""
        if media.cover_color:
            _color = int(media.cover_color.replace("#", ""), 16)
        else:
            _color = discord.Colour.random()
        embed = discord.Embed(
            colour=_color,
            description="",
            url=media.site_url,
            title=media.title.get("english") or media.title.get("romanji") or media.title.get("native"),
        )
        if media.genres:
            embed.description = f"***{', '.join(media.genres)}***\n"
        if media.description:
            embed.description += f"{media.description[:250]}... [(full)]({media.site_url})"
        # from https://github.com/SynderBlack/Tachibot because idk a shit about regex (description with html).
        footer_text += re.sub(r".*\.", "", str(media.status)).replace("_", " ").capitalize()
        if index and total:
            footer_text += f" • Page {index}/{total}"
        if any(media.start_date.values()):
            embed.timestamp = parse(str(media.start_date), fuzzy=True)
        replacements = [
            (r"</?i/?>", ""),
            (r"</?br/?>", "\n")
        ]
        for regex, regex_replace in replacements:
            embed.description = re.sub(regex, regex_replace, embed.description, flags=re.I | re.M)
        embed.set_footer(text=footer_text, icon_url=anilisticon)
        embed.set_image(url=f"https://img.anili.st/media/{media.id}")
        return embed

    @app_commands.command(name='anime')
    @app_commands.describe(name='The name of the anime you want to search')
    async def anime_(self, interaction, name: str) -> discord.Message:
        """Search an anime on https://anilist.co"""
        nsfw_channel = interaction.channel.is_nsfw() if not isinstance(interaction.channel, discord.DMChannel) else False
        try:
            anime = await self.kadalclient.search_anime(name, popularity=True, allow_adult=True)
        except kadal.MediaNotFound:
            return await interaction.response.send_message(self.format_error_message(name))
        stop_if_nsfw(anime.is_adult and not nsfw_channel)
        await interaction.response.send_message(embed=self.format_anilist_embeds(anime))

    @app_commands.command(name='manga')
    @app_commands.describe(name='The name of the manga you want to search')
    async def manga_(self, interaction, name: str) -> discord.Message:
        """Search a manga on https://anilist.co"""
        nsfw_channel = interaction.channel.is_nsfw() if not isinstance(interaction.channel, discord.DMChannel) else False
        try:
            manga = await self.kadalclient.search_manga(name, popularity=True, allow_adult=True)
        except kadal.MediaNotFound:
            return await interaction.response.send_message(self.format_error_message(name))
        stop_if_nsfw(manga.is_adult and not nsfw_channel)
        await interaction.response.send_message(embed=self.format_anilist_embeds(manga))

    @app_commands.command(name='top-manga')
    @app_commands.describe(adult='If you want or not to retrieve adult only mangas')
    async def top_manga_(self, interaction, adult: bool = False):
        """Get the top 50 manga on https://anilist.co"""
        nsfw_channel = interaction.channel.is_nsfw() if not isinstance(interaction.channel, discord.DMChannel) else False
        stop_if_nsfw(adult and not nsfw_channel)
        embed_list = []
        variables = {"type": "MANGA", "sort": "SCORE_DESC"}
        variables["isAdult"] = adult
        allmangas = await self.kadalclient.custom_paged_search(**variables)
        for i, manga in enumerate(allmangas):
            embed_list.append(self.format_anilist_embeds(manga, index=i + 1, total=len(allmangas)))
        await ViewMenu(source=BaseSource(embed_list, per_page=1), main_interaction=interaction).start()

    @app_commands.command(name='top-anime')
    @app_commands.describe(adult='If you want or not to retrieve adult only mangas')
    async def top_anime_(self, interaction, adult: bool = False):
        """Get the top 50 anime on https://anilist.co
        Safe search is forced if not in nsfw channel"""
        nsfw_channel = interaction.channel.is_nsfw() if not isinstance(interaction.channel, discord.DMChannel) else False
        stop_if_nsfw(adult and not nsfw_channel)
        embed_list = []
        variables = {"type": "ANIME", "sort": "SCORE_DESC"}
        variables["isAdult"] = adult
        allanimes = await self.kadalclient.custom_paged_search(**variables)
        for i, anime in enumerate(allanimes):
            embed_list.append(self.format_anilist_embeds(anime, index=i + 1, total=len(allanimes)))
        await ViewMenu(source=BaseSource(embed_list, per_page=1), main_interaction=interaction).start()
