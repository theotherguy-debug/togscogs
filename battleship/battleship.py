import discord
from redbot.core import commands, checks
from .game import GameManager
from .config import DEFAULT_BET

class HackingBattleship(commands.Cog):
    """Hacking‑themed Battleship game cog integrated with TogsCogs."""

    def __init__(self, bot):
        self.bot = bot
        self.manager = GameManager(bot)

    @commands.command(name="battleship_create")
    @checks.bot_has_permissions(send_messages=True)
    async def create(self, ctx, opponent: discord.Member = None, bet: int = DEFAULT_BET):
        """Create a new Battleship match. Use `@bot` for AI or specify a user. Optional bet amount."""
        await self.manager.create_match(ctx, opponent, bet)

    @commands.command(name="battleship_place")
    async def place(self, ctx, coord: str, orientation: str):
        """Place a ship during setup phase. `coord` like A5, `orientation` H/V."""
        await self.manager.place_ship(ctx, coord, orientation)

    @commands.command(name="battleship_attack")
    async def attack(self, ctx, coord: str):
        """Attack a coordinate during your turn."""
        await self.manager.attack(ctx, coord)

    @commands.command(name="battleship_board")
    async def board(self, ctx):
        """Show your board and known opponent hits/misses."""
        await self.manager.show_board(ctx)

    @commands.command(name="battleship_leaderboard")
    async def leaderboard(self, ctx):
        """Display Elo‑ranked leaderboard with wins/losses."""
        await self.manager.show_leaderboard(ctx)

    @commands.command(name="battleship_cancel")
    async def cancel(self, ctx):
        """Cancel a pending game and refund any bet."""
        await self.manager.cancel_match(ctx)

async def setup(bot):
    await bot.add_cog(HackingBattleship(bot))
