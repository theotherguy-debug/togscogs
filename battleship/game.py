# -*- coding: utf-8 -*-
"""Game manager for the Hacking Battleship cog.

This class coordinates matches, stores active game states, and delegates
logic to the lower‑level engine modules (game_logic, bot_ai, etc.).
It is intentionally lightweight – most heavy work is done in the
individual GameState objects.
"""

import asyncio
from typing import Dict, Optional

import discord
from redbot.core import commands

from .game_logic import GameState
from .bot_ai import RandomBotAI

class GameManager:
    """Manages active Battleship games.

    Attributes
    ----------
    bot: commands.Bot
        The Red‑DiscordBot instance.
    active_games: Dict[int, GameState]
        Mapping from channel ID to the current GameState.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[int, GameState] = {}
        self.bot.loop.create_task(self._cleanup_task())

    async def _cleanup_task(self) -> None:
        """Periodically remove stale games (e.g., after timeout)."""
        while True:
            await asyncio.sleep(300)  # run every 5 minutes
            now = asyncio.get_event_loop().time()
            to_remove = []
            for channel_id, game in self.active_games.items():
                if now - game.last_activity > 1800:  # 30‑minute inactivity
                    to_remove.append(channel_id)
            for cid in to_remove:
                del self.active_games[cid]

    async def create_match(self, ctx: commands.Context, opponent: Optional[discord.Member], bet: int) -> None:
        """Create a new match or raise an informative error.
        """
        channel_id = ctx.channel.id
        if channel_id in self.active_games:
            await ctx.send("A game is already in progress in this channel.")
            return
        # Initialize GameState – handles economy, betting, etc.
        game = GameState(self.bot, ctx.author, opponent, bet)
        self.active_games[channel_id] = game
        await game.start()

    async def place_ship(self, ctx: commands.Context, coord: str, orientation: str) -> None:
        game = self.active_games.get(ctx.channel.id)
        if not game:
            await ctx.send("No active game in this channel. Use `battleship_create` first.")
            return
        await game.place_ship(ctx.author, coord, orientation)

    async def attack(self, ctx: commands.Context, coord: str) -> None:
        game = self.active_games.get(ctx.channel.id)
        if not game:
            await ctx.send("No active game in this channel.")
            return
        await game.attack(ctx.author, coord)
        # Clean up finished games
        if game.is_finished:
            del self.active_games[ctx.channel.id]

    async def show_board(self, ctx: commands.Context) -> None:
        game = self.active_games.get(ctx.channel.id)
        if not game:
            await ctx.send("No active game in this channel.")
            return
        await game.display_board(ctx.author)

    async def show_leaderboard(self, ctx: commands.Context) -> None:
        # Simple wrapper – GameState handles fetching stats from DB
        await GameState.display_leaderboard(self.bot, ctx)

    async def cancel_match(self, ctx: commands.Context) -> None:
        game = self.active_games.pop(ctx.channel.id, None)
        if not game:
            await ctx.send("No active game to cancel.")
            return
        await game.cancel()
        await ctx.send("Game cancelled and any bets have been refunded.")
