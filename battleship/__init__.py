from .battleship import HackingBattleship

async def setup(bot):
    await bot.add_cog(HackingBattleship(bot))
