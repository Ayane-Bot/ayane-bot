import discord
from discord.ext import commands

from main import Ayane
from utils import defaults
from utils.context import AyaneContext
from utils.paginators import BaseSource, ViewMenu

import kadal
# fork at https://github.com/Bucolo/Kadal/
import re
from dateutil.parser import parse


def setup(bot):
    bot.add_cog(Fun(bot))


anilisticon = "https://www.gitbook.com/cdn-cgi/image/" \
              "width=40,height=40,fit=contain,dpr=1," \
              "format=auto/https%3A%2F%2Fanilist.gitbook.io%2F~%2Ffiles%2Fv0%2Fb%2Fgitbook-28427.appspot.com" \
              "%2Fo%2Fspaces%252F-LHizcWWtVphqU90YAXO%252Favatar.png" \
              "%3Fgeneration%3D1531944291782256%26alt%3Dmedia"


class Fun(defaults.AyaneCog, emoji='🎢', brief='Some fun commands'):
    def __init__(self, bot):
        self.bot: Ayane = bot
        self.kadalclient = kadal.Client(session=self.bot.session, loop=self.bot.loop)

    @staticmethod
    def format_error_message(search, safe_search=False):
        error_message = f"Sorry I did not find anything that match your search `{search}`\n\n"
        if safe_search:
            error_message += "*The safe search is active, you may want to try in an nsfw-channel to disable it.*"
        return error_message

    @staticmethod
    def format_anilist_embeds(media, is_nsfw, index=0, total=0):
        footer_text = "Safe Search • " if not is_nsfw else ""
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

    @defaults.ayane_command(name='anime', aliases=['anm'])
    async def anime_(self, ctx: AyaneContext, *, name) -> discord.Message:
        """Search an anime on https://anilist.co"""
        try:
            anime = await self.kadalclient.search_anime(name, popularity=True, allow_adult=True)
        except kadal.MediaNotFound:
            return await ctx.send(self.format_error_message(name, safe_search=False))
        ctx.stop_if_nsfw(anime.is_adult)
        await ctx.send(embed=self.format_anilist_embeds(anime, is_nsfw))

    @defaults.ayane_command(name='manga',
                            aliases=['mng', 'mang', 'webtton', 'comic', 'manhua', 'manhwa', 'pornhwa', 'pornhua'])
    async def manga_(self, ctx: AyaneContext, *, name) -> discord.Message:
        """Search a manga on https://anilist.co"""
        try:
            manga = await self.kadalclient.search_manga(name, popularity=True, allow_adult=True)
        except kadal.MediaNotFound:
            return await ctx.send(self.format_error_message(name, safe_search=False))
        ctx.stop_if_nsfw(manga.is_adult)
        await ctx.send(embed=self.format_anilist_embeds(manga, is_nsfw))

    @defaults.ayane_command(
        name='topmanga',
        aliases=[
            'topmng',
            'topmang',
            'topwebtton',
            'topcomic',
            'topmanhua',
            'topmanhwa',
            'toppornhwa',
            'toppornhua'
        ]
    )
    async def topmanga_(
            self,
            ctx: AyaneContext,
            adult: bool = commands.Option(
                default=None,
                description="Whether you want the top to contain only adult manga",
            ),
    ) -> discord.Message:
        """Get the top 50 manga on https://anilist.co
        Safe search is forced if not in nsfw channel"""
        ctx.stop_if_nsfw(adult)
        embed_list = []
        is_nsfw = False
        if isinstance(ctx.channel, (discord.Thread, discord.TextChannel)):
            is_nsfw = ctx.channel.is_nsfw()
        variables = {"type": "MANGA", "sort": "SCORE_DESC"}
        if not is_nsfw:
            variables["isAdult"] = is_nsfw
        elif adult is not None:
            variables["isAdult"] = adult
        allmangas = await self.kadalclient.custom_paged_search(**variables)
        for i, manga in enumerate(allmangas):
            embed_list.append(self.format_anilist_embeds(manga, is_nsfw, index=i + 1, total=len(allmangas)))
        await ViewMenu(source=BaseSource(embed_list, per_page=1), ctx=ctx).start()

    @defaults.ayane_command(name='topanime', aliases=['topanm'])
    async def topanime_(
            self,
            ctx: AyaneContext,
            adult: bool = commands.Option(
                default=None,
                description="Whether you want the top to contain only adult anime",
            ),
    ) -> discord.Message:
        """Get the top 50 anime on https://anilist.co
        Safe search is forced if not in nsfw channel"""
        ctx.stop_if_nsfw(adult)
        embed_list = []
        is_nsfw = False
        if isinstance(ctx.channel, (discord.Thread, discord.TextChannel)):
            is_nsfw = ctx.channel.is_nsfw()
        variables = {"type": "ANIME", "sort": "SCORE_DESC"}
        if not is_nsfw:
            variables["isAdult"] = is_nsfw
        elif adult is not None:
            variables["isAdult"] = adult
        allanimes = await self.kadalclient.custom_paged_search(**variables)
        for i, anime in enumerate(allanimes):
            embed_list.append(self.format_anilist_embeds(anime, is_nsfw, index=i + 1, total=len(allanimes)))
        await ViewMenu(source=BaseSource(embed_list, per_page=1), ctx=ctx).start()
