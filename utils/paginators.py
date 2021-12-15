import discord
from discord.ext import menus

from utils.constants import DomainBaseURL


class BaseSource(menus.ListPageSource):
    """Subclassing to change the way some method where coded
    (ex: get_max_pages not giving 'current' max pages)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def format_page(self, menu, entries):
        return entries

    def is_paginating(self):
        return len(self.entries) > 1

    def get_max_pages(self):
        pages, left_over = divmod(len(self.entries), self.per_page)
        if left_over:
            pages += 1
        self._max_pages = pages
        return self._max_pages


class ImageSource(BaseSource):
    def __init__(
            self,
            image_info,
            user=None,
            request_time=None,
            title="Not Assigned",
            **kwargs,
    ):
        self.image_info = image_info
        self.title = title
        self.user = user
        self.request_time = request_time
        self.many = len(self.image_info) > 1
        embed_source = self.format_embeds()
        super().__init__(embed_source, **kwargs)

    def remove(self, index):
        """remove a picture from the image source and re-format the embeds to display"""
        del self.image_info[index]
        self.many = len(self.image_info) > 1
        self.entries = self.format_embeds()

    def get_infos(self, index):
        return self.image_info[index]

    def format_embeds(self):
        embed_list = []
        for i, im in enumerate(self.image_info):
            embed = discord.Embed(
                url=im["url"], colour=int(im["dominant_color"].replace("#", ""), 16)
            )
            embed.set_author(
                name=self.title,
                url=f"https://{DomainBaseURL}/preview/?image=" + im["file"] + im["extension"],
            )
            embed.set_image(url=im["url"])
            text = f"Requested by {self.user.name}"
            if self.request_time:
                text += f" | {self.request_time}s"
            if self.many:
                text += f" | {i + 1}/{len(self.image_info)}"

            embed.set_footer(text=text, icon_url=self.user.display_avatar.url)
            embed_list.append(embed)
        return embed_list


