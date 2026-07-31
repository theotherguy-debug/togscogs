from .netrank import NetRank

async def setup(bot):
    cog = NetRank(bot)
    await bot.add_cog(cog)
