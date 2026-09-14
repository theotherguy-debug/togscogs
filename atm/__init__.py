from .atm import ATM

async def setup(bot):
    await bot.add_cog(ATM(bot))
