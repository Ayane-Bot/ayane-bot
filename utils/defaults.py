from discord.ext.commands import Cog


class AyaneCog(Cog):
    def __init_subclass__(cls, **kwargs):
        cls.emoji = kwargs.pop('emoji', None)
        cls.brief = kwargs.pop('brief', None)
        cls.icon = kwargs.pop('icon', None)
        super().__init_subclass__(**kwargs)
