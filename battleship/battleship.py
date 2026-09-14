import asyncio
import random
import time
from typing import Dict, List, Optional, Tuple

import discord
from discord import ui
from redbot.core import commands, Config, bank, app_commands


# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
GRID_SIZE = 10
LETTERS = "ABCDEFGHIJ"

SHIP_DEFS = {
    "Mainframe":  5,   # Carrier
    "Firewall":   4,   # Battleship
    "Proxy":      3,   # Cruiser
    "Rootkit":    3,   # Submarine
    "Exploit":    2,   # Destroyer
}

TURN_TIMEOUT = 120   # seconds
ELO_K = 32
WIN_REWARD = 100
DEFAULT_BET = 0
HOUSE_FEE_PERCENT = 0

# Emoji legend
WATER   = "🟦"
SHIP    = "⬜"
HIT     = "🟥"
MISS    = "⬛"
SUNK    = "💀"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def parse_coord(raw: str) -> Optional[Tuple[int, int]]:
    """Parse 'A5' -> (row=0, col=4). Returns None on bad input."""
    raw = raw.strip().upper()
    if len(raw) < 2 or len(raw) > 3:
        return None
    letter = raw[0]
    if letter not in LETTERS:
        return None
    try:
        col = int(raw[1:]) - 1
    except ValueError:
        return None
    row = LETTERS.index(letter)
    if not (0 <= col < GRID_SIZE):
        return None
    return (row, col)


def coord_label(row: int, col: int) -> str:
    return f"{LETTERS[row]}{col + 1}"


def render_grid_text(grid: List[List[str]]) -> str:
    """Render a grid as a fixed-width text block."""
    header = "   " + "  ".join(str(i + 1).rjust(2) for i in range(GRID_SIZE))
    lines = [header]
    for r in range(GRID_SIZE):
        row_str = f" {LETTERS[r]} " + " ".join(grid[r])
        lines.append(row_str)
    return "\n".join(lines)


def make_grid_embed(
    own_board: List[List[str]],
    tracking_board: List[List[str]],
    player_name: str,
    title: str = "Battleship Console",
    footer: str = "",
) -> discord.Embed:
    """Build a Discord embed showing both grids."""
    embed = discord.Embed(title=f"🖥️ {title}", color=discord.Color.dark_green())
    embed.add_field(name=f"🛡️ {player_name}'s Network", value=render_grid_text(own_board), inline=False)
    embed.add_field(name="📡 Enemy Network (Fog of War)", value=render_grid_text(tracking_board), inline=False)
    if footer:
        embed.set_footer(text=footer)
    return embed


def make_single_grid_embed(
    grid: List[List[str]],
    player_name: str,
    title: str = "",
    footer: str = "",
    color: discord.Color = discord.Color.dark_green(),
) -> discord.Embed:
    """Embed showing a single grid."""
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name=f"🛡️ {player_name}'s Network", value=render_grid_text(grid), inline=False)
    if footer:
        embed.set_footer(text=footer)
    return embed


def elo_update(elo_a: float, elo_b: float, a_won: bool) -> Tuple[float, float]:
    """Standard Elo calculation.  Returns (new_elo_a, new_elo_b)."""
    ea = 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))
    eb = 1.0 - ea
    sa = 1.0 if a_won else 0.0
    sb = 1.0 - sa
    return (elo_a + ELO_K * (sa - ea), elo_b + ELO_K * (sb - eb))


# ---------------------------------------------------------------------------
# Board / Ship helpers
# ---------------------------------------------------------------------------
class Ship:
    __slots__ = ("name", "length", "cells", "hits")

    def __init__(self, name: str, length: int):
        self.name = name
        self.length = length
        self.cells: List[Tuple[int, int]] = []
        self.hits: List[bool] = []

    @property
    def is_sunk(self) -> bool:
        return all(self.hits)


class Board:
    """10x10 board for a single player."""

    def __init__(self):
        self.grid: List[List[Optional[Ship]]] = [
            [None] * GRID_SIZE for _ in range(GRID_SIZE)
        ]
        self.ships: List[Ship] = []
        self.shots: List[List[Optional[bool]]] = [
            [None] * GRID_SIZE for _ in range(GRID_SIZE)
        ]  # True=hit, False=miss, None=unknown (incoming shots)
        self.ship_queue: List[Tuple[str, int]] = list(SHIP_DEFS.items())
        self.all_placed = False

    @property
    def next_ship(self) -> Optional[Tuple[str, int]]:
        return self.ship_queue[0] if self.ship_queue else None

    def place_ship(
        self, name: str, length: int, row: int, col: int, horizontal: bool
    ) -> bool:
        """Try to place a ship.  Returns True on success."""
        cells: List[Tuple[int, int]] = []
        for i in range(length):
            r = row if horizontal else row + i
            c = col + i if horizontal else col
            if not (0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE):
                return False
            if self.grid[r][c] is not None:
                return False
            cells.append((r, c))

        ship = Ship(name, length)
        ship.cells = cells
        ship.hits = [False] * length
        for r, c in cells:
            self.grid[r][c] = ship
        self.ships.append(ship)
        self.ship_queue.pop(0)
        if not self.ship_queue:
            self.all_placed = True
        return True

    def receive_attack(self, row: int, col: int) -> Tuple[str, Optional[Ship]]:
        """Process an incoming attack.  Returns ('hit'/'miss'/'sunk', ship_or_None)."""
        if self.shots[row][col] is not None:
            return ("already", None)
        ship = self.grid[row][col]
        if ship is None:
            self.shots[row][col] = False
            return ("miss", None)
        idx = ship.cells.index((row, col))
        ship.hits[idx] = True
        self.shots[row][col] = True
        if ship.is_sunk:
            return ("sunk", ship)
        return ("hit", ship)

    @property
    def all_sunk(self) -> bool:
        return all(s.is_sunk for s in self.ships)

    def render_own(self) -> List[List[str]]:
        """Grid showing your own ships + incoming hits/misses."""
        out = [[WATER] * GRID_SIZE for _ in range(GRID_SIZE)]
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                ship = self.grid[r][c]
                shot = self.shots[r][c]
                if shot is True:
                    out[r][c] = HIT if ship else MISS
                elif shot is False:
                    out[r][c] = MISS
                elif ship is not None:
                    out[r][c] = SUNK if ship.is_sunk else SHIP
        return out

    def render_tracking(self) -> List[List[str]]:
        """Fog-of-war grid showing only hits/misses from outgoing attacks."""
        out = [[WATER] * GRID_SIZE for _ in range(GRID_SIZE)]
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                shot = self.shots[r][c]
                if shot is True:
                    ship = self.grid[r][c]
                    out[r][c] = SUNK if (ship and ship.is_sunk) else HIT
                elif shot is False:
                    out[r][c] = MISS
        return out

    def render_reveal(self) -> List[List[str]]:
        """Full reveal of this board — shows all ships plus hits/misses."""
        out = [[WATER] * GRID_SIZE for _ in range(GRID_SIZE)]
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                ship = self.grid[r][c]
                shot = self.shots[r][c]
                if shot is True and ship:
                    out[r][c] = SUNK if ship.is_sunk else HIT
                elif shot is False:
                    out[r][c] = MISS
                elif ship is not None:
                    out[r][c] = SHIP
        return out

    def random_place_all(self):
        """Auto-place all remaining ships randomly."""
        while self.ship_queue:
            name, length = self.ship_queue[0]
            placed = False
            attempts = 0
            while not placed and attempts < 200:
                horizontal = random.choice([True, False])
                row = random.randint(0, GRID_SIZE - 1)
                col = random.randint(0, GRID_SIZE - 1)
                placed = self.place_ship(name, length, row, col, horizontal)
                attempts += 1


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------
class GameSession:
    """Holds the state for one Battleship match."""

    def __init__(
        self,
        channel: discord.TextChannel,
        player1: discord.Member,
        player2: Optional[discord.Member],
        bet: int,
        is_bot: bool,
    ):
        self.channel = channel
        self.player1 = player1
        self.player2 = player2
        self.bet = bet
        self.is_bot = is_bot

        self.boards: Dict[int, Board] = {
            player1.id: Board(),
        }
        if player2:
            self.boards[player2.id] = Board()
        else:
            # Bot board
            self.boards[0] = Board()
            self.boards[0].random_place_all()

        self.phase = "setup"  # setup | playing | finished
        self.turn: int = player1.id   # whose turn
        self.last_activity: float = time.time()
        # Track which players have confirmed placement
        self.ready: Dict[int, bool] = {player1.id: False}
        if player2:
            self.ready[player2.id] = False

    @property
    def is_finished(self) -> bool:
        return self.phase == "finished"

    def opponent_id(self, player_id: int) -> int:
        if player_id == self.player1.id:
            return self.player2.id if self.player2 else 0
        return self.player1.id

    def both_placed(self) -> bool:
        return all(b.all_placed for b in self.boards.values())

    def both_ready(self) -> bool:
        return all(self.ready.values())

    def switch_turn(self):
        self.turn = self.opponent_id(self.turn)


# ---------------------------------------------------------------------------
# Ship placement view — fully button/dropdown driven
# ---------------------------------------------------------------------------
class PlacementRowSelect(ui.Select):
    """Dropdown to pick a row (A-J)."""
    def __init__(self):
        options = [discord.SelectOption(label=f"Row {LETTERS[i]}", value=str(i)) for i in range(GRID_SIZE)]
        super().__init__(placeholder="Select Row (A-J)", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_row = int(self.values[0])
        await interaction.response.defer()


class PlacementColSelect(ui.Select):
    """Dropdown to pick a column (1-10)."""
    def __init__(self):
        options = [discord.SelectOption(label=f"Col {i+1}", value=str(i)) for i in range(GRID_SIZE)]
        super().__init__(placeholder="Select Column (1-10)", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_col = int(self.values[0])
        await interaction.response.defer()


class PlacementView(ui.View):
    """Interactive ship placement using dropdowns and buttons."""
    def __init__(self, cog, session: GameSession, player: discord.Member):
        super().__init__(timeout=300)
        self.cog = cog
        self.session = session
        self.player = player
        self.message: Optional[discord.Message] = None
        self.selected_row: Optional[int] = None
        self.selected_col: Optional[int] = None
        self.orientation = "H"

        self.add_item(PlacementRowSelect())
        self.add_item(PlacementColSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player.id:
            await interaction.response.send_message("This isn't your console.", ephemeral=True)
            return False
        return True

    def _build_embed(self) -> discord.Embed:
        board = self.session.boards[self.player.id]
        own = board.render_own()
        nxt = board.next_ship
        if nxt:
            footer = (
                f"Next: {nxt[0]} (length {nxt[1]}) | "
                f"Orientation: {'Horizontal ➡️' if self.orientation == 'H' else 'Vertical ⬇️'}"
            )
            if self.selected_row is not None and self.selected_col is not None:
                footer += f" | Selected: {coord_label(self.selected_row, self.selected_col)}"
        else:
            footer = "✅ All ships placed! Hit Confirm when ready."

        return make_single_grid_embed(
            own, self.player.display_name,
            title="🚢 Ship Deployment Console",
            footer=footer,
        )

    @ui.button(label="Horizontal ➡️", style=discord.ButtonStyle.primary, row=2)
    async def set_horizontal(self, interaction: discord.Interaction, button: ui.Button):
        self.orientation = "H"
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @ui.button(label="Vertical ⬇️", style=discord.ButtonStyle.primary, row=2)
    async def set_vertical(self, interaction: discord.Interaction, button: ui.Button):
        self.orientation = "V"
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @ui.button(label="Place Ship", style=discord.ButtonStyle.success, emoji="📌", row=2)
    async def place_btn(self, interaction: discord.Interaction, button: ui.Button):
        board = self.session.boards[self.player.id]
        nxt = board.next_ship
        if nxt is None:
            await interaction.response.send_message("All ships already placed!", ephemeral=True)
            return
        if self.selected_row is None or self.selected_col is None:
            await interaction.response.send_message("Select a row AND column first!", ephemeral=True)
            return

        name, length = nxt
        horiz = self.orientation == "H"
        if not board.place_ship(name, length, self.selected_row, self.selected_col, horiz):
            await interaction.response.send_message(
                f"```[ERROR]: Can't place {name} at {coord_label(self.selected_row, self.selected_col)} "
                f"({'H' if horiz else 'V'}) – out of bounds or overlapping.```",
                ephemeral=True,
            )
            return

        self.selected_row = None
        self.selected_col = None
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @ui.button(label="Auto-Place All 🎲", style=discord.ButtonStyle.secondary, row=3)
    async def auto_place(self, interaction: discord.Interaction, button: ui.Button):
        board = self.session.boards[self.player.id]
        board.random_place_all()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @ui.button(label="✅ Confirm Setup", style=discord.ButtonStyle.success, row=3)
    async def confirm_btn(self, interaction: discord.Interaction, button: ui.Button):
        board = self.session.boards[self.player.id]
        if not board.all_placed:
            await interaction.response.send_message("Place all your ships first!", ephemeral=True)
            return

        self.session.ready[self.player.id] = True

        # Disable all buttons
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=self._build_embed(), view=self)
        await self.session.channel.send(
            f"```[READY]: {self.player.display_name} has deployed all servers. ✅```"
        )
        await self.cog._check_setup_complete(self.session)
        self.stop()


# ---------------------------------------------------------------------------
# Attack view — dropdown-based coordinate selection
# ---------------------------------------------------------------------------
class AttackRowSelect(ui.Select):
    """Dropdown to pick a row (A-J) for attack."""
    def __init__(self):
        options = [discord.SelectOption(label=f"Row {LETTERS[i]}", value=str(i)) for i in range(GRID_SIZE)]
        super().__init__(placeholder="Select Row (A-J)", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_row = int(self.values[0])
        await interaction.response.defer()


class AttackColSelect(ui.Select):
    """Dropdown to pick a column (1-10) for attack."""
    def __init__(self):
        options = [discord.SelectOption(label=f"Col {i+1}", value=str(i)) for i in range(GRID_SIZE)]
        super().__init__(placeholder="Select Column (1-10)", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_col = int(self.values[0])
        await interaction.response.defer()


class BattleView(ui.View):
    """Interactive attack view with dropdowns + fire button."""
    def __init__(self, cog, session: GameSession):
        super().__init__(timeout=TURN_TIMEOUT)
        self.cog = cog
        self.session = session
        self.message: Optional[discord.Message] = None
        self.selected_row: Optional[int] = None
        self.selected_col: Optional[int] = None

        self.add_item(AttackRowSelect())
        self.add_item(AttackColSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.session.turn:
            await interaction.response.send_message("It's not your turn, operator.", ephemeral=True)
            return False
        return True

    @ui.button(label="🔥 Launch Exploit", style=discord.ButtonStyle.danger, row=2)
    async def fire_btn(self, interaction: discord.Interaction, button: ui.Button):
        if self.selected_row is None or self.selected_col is None:
            await interaction.response.send_message(
                "Select a **row** and **column** from the dropdowns first!", ephemeral=True
            )
            return
        # Disable view after firing
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        await self.cog._resolve_attack(
            self.session, interaction.user.id, self.selected_row, self.selected_col
        )
        self.stop()

    @ui.button(label="📊 My Board", style=discord.ButtonStyle.primary, row=2)
    async def board_btn(self, interaction: discord.Interaction, button: ui.Button):
        player_id = interaction.user.id
        own_board = self.session.boards[player_id]
        opp_board = self.session.boards[self.session.opponent_id(player_id)]
        embed = make_grid_embed(
            own_board.render_own(),
            opp_board.render_tracking(),
            interaction.user.display_name,
            title="Your Operator Console",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label="🏳️ Surrender", style=discord.ButtonStyle.secondary, row=2)
    async def surrender_btn(self, interaction: discord.Interaction, button: ui.Button):
        self.session.phase = "finished"
        for item in self.children:
            item.disabled = True
        winner_id = self.session.opponent_id(interaction.user.id)
        await interaction.response.edit_message(view=self)
        self.active_games_ref = self.cog.active_games
        self.active_games_ref.pop(self.session.channel.id, None)
        await self.cog._finish_game(self.session, winner_id, surrendered=True)
        self.stop()

    async def on_timeout(self):
        if self.session.phase == "finished":
            return
        self.session.phase = "finished"
        winner_id = self.session.opponent_id(self.session.turn)
        self.cog.active_games.pop(self.session.channel.id, None)
        await self.cog._finish_game(self.session, winner_id, timeout=True)


# ---------------------------------------------------------------------------
# Main Cog
# ---------------------------------------------------------------------------
class HackingBattleship(commands.Cog):
    """Hacking-themed Battleship game with Elo, economy, and betting."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=84729384729, force_registration=True)
        self.config.register_user(wins=0, losses=0, elo=1200.0)
        self.active_games: Dict[int, GameSession] = {}

    # ---------- Create ----------
    @commands.hybrid_command(name="battleship")
    @app_commands.describe(
        opponent="The user to challenge, or leave blank for AI.",
        bet="Optional bet amount in credits.",
    )
    @commands.guild_only()
    async def battleship_create(
        self, ctx: commands.Context,
        opponent: Optional[discord.Member] = None,
        bet: int = DEFAULT_BET,
    ):
        """Start a new Hacking Battleship match.

        Challenge another user or play against the bot AI.
        Optionally place a bet – the winner takes the pot plus a flat reward.
        """
        channel_id = ctx.channel.id
        if channel_id in self.active_games:
            await ctx.send("```[ERROR]: A game is already active in this channel.```")
            return

        is_bot_game = opponent is None or opponent.bot
        if opponent and opponent.id == ctx.author.id:
            await ctx.send("```[ERROR]: Cannot challenge yourself.```")
            return

        # Validate bet
        if bet < 0:
            await ctx.send("```[ERROR]: Bet cannot be negative.```")
            return

        guild = ctx.guild
        currency_name = "credits"
        try:
            currency_name = await bank.get_currency_name(guild)
        except Exception:
            pass

        if bet > 0:
            try:
                author_bal = await bank.get_balance(ctx.author)
                if author_bal < bet:
                    await ctx.send(f"```[ERROR]: Insufficient {currency_name}. You have {author_bal}.```")
                    return
                if not is_bot_game:
                    opp_bal = await bank.get_balance(opponent)
                    if opp_bal < bet:
                        await ctx.send(f"```[ERROR]: {opponent.display_name} has insufficient {currency_name}.```")
                        return
                # Withdraw bets
                await bank.withdraw_credits(ctx.author, bet)
                if not is_bot_game:
                    await bank.withdraw_credits(opponent, bet)
            except Exception as e:
                await ctx.send(f"```[ERROR]: Economy error – {e}```")
                return

        session = GameSession(
            ctx.channel, ctx.author,
            None if is_bot_game else opponent,
            bet, is_bot_game,
        )
        self.active_games[channel_id] = session

        # Announce
        opp_name = "🤖 Bot AI" if is_bot_game else opponent.mention
        bet_text = f" | Bet: {bet} {currency_name} each" if bet > 0 else ""

        embed = discord.Embed(
            title="⚔️ HACKING BATTLESHIP – MATCH CREATED",
            description=(
                f"**Attacker:** {ctx.author.mention}\n"
                f"**Defender:** {opp_name}\n"
                f"**Grid:** {GRID_SIZE}×{GRID_SIZE}{bet_text}\n\n"
                "Deploy your servers using the dropdowns below.\n"
                "Select **Row**, **Column**, and **Orientation**, then press **Place Ship**.\n"
                "Or hit **Auto-Place All** for a quick random setup.\n"
                "Press **✅ Confirm Setup** when you're done."
            ),
            color=discord.Color.dark_green(),
        )
        await ctx.send(embed=embed)

        # Send placement view for player 1
        view1 = PlacementView(self, session, ctx.author)
        msg1 = await ctx.send(
            f"{ctx.author.mention} — Deploy your servers:",
            embed=view1._build_embed(), view=view1,
        )
        view1.message = msg1

        # Send placement view for player 2 (if PvP)
        if not is_bot_game and opponent:
            view2 = PlacementView(self, session, opponent)
            msg2 = await ctx.send(
                f"{opponent.mention} — Deploy your servers:",
                embed=view2._build_embed(), view=view2,
            )
            view2.message = msg2

    # ---------- Text fallback: place ----------
    @commands.hybrid_command(name="bsplace")
    @app_commands.describe(coord="Grid coordinate, e.g. A5", orientation="H for horizontal, V for vertical")
    @commands.guild_only()
    async def battleship_place(self, ctx: commands.Context, coord: str, orientation: str):
        """Place your next ship at the given coordinate (text fallback).

        Orientation is H (horizontal) or V (vertical).
        """
        session = self.active_games.get(ctx.channel.id)
        if not session:
            await ctx.send("```[ERROR]: No active game in this channel.```")
            return
        if session.phase != "setup":
            await ctx.send("```[ERROR]: Ship placement phase is over.```")
            return

        player_id = ctx.author.id
        board = session.boards.get(player_id)
        if board is None:
            await ctx.send("```[ERROR]: You are not part of this game.```")
            return
        nxt = board.next_ship
        if nxt is None:
            await ctx.send("```[INFO]: All your ships are already placed.```")
            return

        parsed = parse_coord(coord)
        if parsed is None:
            await ctx.send("```[ERROR]: Invalid coordinate.```")
            return
        row, col = parsed
        horiz = orientation.strip().upper().startswith("H")

        name, length = nxt
        if not board.place_ship(name, length, row, col, horiz):
            await ctx.send("```[ERROR]: Cannot place ship there – out of bounds or overlapping.```")
            return

        own = board.render_own()
        tracking = [[WATER] * GRID_SIZE for _ in range(GRID_SIZE)]
        nxt2 = board.next_ship
        footer = f"Next: {nxt2[0]} (length {nxt2[1]})" if nxt2 else "All ships placed! Use ✅ Confirm Setup."
        embed = make_single_grid_embed(own, ctx.author.display_name,
                                       title="🚢 Ship Deployment Console", footer=footer)
        await ctx.send(embed=embed)

    # ---------- Text fallback: attack ----------
    @commands.hybrid_command(name="bsattack")
    @app_commands.describe(coord="Target coordinate, e.g. A5")
    @commands.guild_only()
    async def battleship_attack(self, ctx: commands.Context, coord: str):
        """Launch an exploit at the given coordinate (text fallback)."""
        session = self.active_games.get(ctx.channel.id)
        if not session:
            await ctx.send("```[ERROR]: No active game in this channel.```")
            return
        if session.phase != "playing":
            await ctx.send("```[ERROR]: Game is not in the attack phase.```")
            return
        if ctx.author.id != session.turn:
            await ctx.send("```[ERROR]: It's not your turn.```")
            return

        parsed = parse_coord(coord)
        if parsed is None:
            await ctx.send("```[ERROR]: Invalid coordinate.```")
            return
        row, col = parsed
        await self._resolve_attack(session, ctx.author.id, row, col)

    # ---------- Board view ----------
    @commands.hybrid_command(name="bsboard")
    @commands.guild_only()
    async def battleship_board(self, ctx: commands.Context):
        """View your current board and known enemy hits/misses."""
        session = self.active_games.get(ctx.channel.id)
        if not session:
            await ctx.send("```[ERROR]: No active game in this channel.```")
            return
        player_id = ctx.author.id
        board = session.boards.get(player_id)
        if board is None:
            await ctx.send("```[ERROR]: You are not part of this game.```")
            return
        opp_board = session.boards[session.opponent_id(player_id)]
        embed = make_grid_embed(
            board.render_own(),
            opp_board.render_tracking(),
            ctx.author.display_name,
            title="Your Operator Console",
        )
        await ctx.send(embed=embed)

    # ---------- Cancel ----------
    @commands.hybrid_command(name="bscancel")
    @commands.guild_only()
    async def battleship_cancel(self, ctx: commands.Context):
        """Cancel the current game and refund any bets."""
        session = self.active_games.pop(ctx.channel.id, None)
        if not session:
            await ctx.send("```[ERROR]: No active game to cancel.```")
            return

        # Refund bets
        if session.bet > 0:
            try:
                await bank.deposit_credits(session.player1, session.bet)
                if session.player2:
                    await bank.deposit_credits(session.player2, session.bet)
            except Exception:
                pass

        await ctx.send("```[ABORT]: Game cancelled. All bets refunded.```")

    # ---------- Leaderboard ----------
    @commands.hybrid_command(name="bsleaderboard")
    @commands.guild_only()
    async def battleship_leaderboard(self, ctx: commands.Context):
        """Display the Battleship Elo leaderboard with wins/losses."""
        all_users = await self.config.all_users()
        if not all_users:
            await ctx.send("```[LOG]: No matches recorded yet.```")
            return

        sorted_users = sorted(all_users.items(), key=lambda x: -x[1].get("elo", 1200))[:10]

        text = "╔═══════════ BATTLESHIP LEADERBOARD ═══════════╗\n"
        text += "║  #  │ Operator             │  Elo  │  W │  L  ║\n"
        text += "╠═════╪══════════════════════╪═══════╪════╪═════╣\n"

        for i, (uid, data) in enumerate(sorted_users, 1):
            try:
                user = await self.bot.fetch_user(int(uid))
                name = user.name[:20]
            except Exception:
                name = f"User_{uid}"
            elo = int(data.get("elo", 1200))
            wins = data.get("wins", 0)
            losses = data.get("losses", 0)
            text += f"║ {str(i).rjust(2)}  │ {name.ljust(20)} │ {str(elo).rjust(5)} │ {str(wins).rjust(2)} │ {str(losses).rjust(3)} ║\n"

        text += "╚═══════════════════════════════════════════════╝"
        await ctx.send(f"```\n{text}\n```")

    # ---------- Internal helpers ----------
    async def _check_setup_complete(self, session: GameSession):
        """If all players have placed + confirmed, transition to the attack phase."""
        if not session.both_placed() or not session.both_ready():
            return
        session.phase = "playing"
        session.turn = session.player1.id

        # Show both setups to the channel before battle begins
        p1_board = session.boards[session.player1.id]
        p1_name = session.player1.display_name

        embed1 = make_single_grid_embed(
            p1_board.render_own(), p1_name,
            title=f"🛡️ {p1_name}'s Server Layout",
            color=discord.Color.blue(),
        )
        await session.channel.send(embed=embed1)

        if session.is_bot:
            bot_board = session.boards[0]
            embed_bot = make_single_grid_embed(
                bot_board.render_own(), "🤖 Bot AI",
                title="🛡️ Bot AI's Server Layout",
                color=discord.Color.red(),
            )
            await session.channel.send(embed=embed_bot)
        elif session.player2:
            p2_board = session.boards[session.player2.id]
            p2_name = session.player2.display_name
            embed2 = make_single_grid_embed(
                p2_board.render_own(), p2_name,
                title=f"🛡️ {p2_name}'s Server Layout",
                color=discord.Color.red(),
            )
            await session.channel.send(embed=embed2)

        # Battle starts
        turn_name = session.player1.display_name

        embed = discord.Embed(
            title="🔥 ALL SERVERS DEPLOYED – BATTLE BEGINS",
            description=(
                "All ships are in position. Both setups revealed!\n\n"
                f"**{turn_name}** goes first.\n"
                "Select **Row** and **Column** from the dropdowns, then press **🔥 Launch Exploit**."
            ),
            color=discord.Color.red(),
        )
        await session.channel.send(embed=embed)

        view = BattleView(self, session)
        msg = await session.channel.send(
            f"⏳ **{turn_name}** — your turn to attack!", view=view,
        )
        view.message = msg

    async def _resolve_attack(self, session: GameSession, attacker_id: int, row: int, col: int):
        """Process an attack and handle the result."""
        defender_id = session.opponent_id(attacker_id)
        defender_board = session.boards[defender_id]

        result, ship = defender_board.receive_attack(row, col)
        session.last_activity = time.time()
        target = coord_label(row, col)

        if result == "already":
            await session.channel.send(f"```[ERROR]: Coordinate {target} already targeted.```")
            # Re-send the battle view so they can pick again
            view = BattleView(self, session)
            msg = await session.channel.send("Pick a different target:", view=view)
            view.message = msg
            return

        # Build result message
        if result == "miss":
            log = f"[EXPLOIT → {target}]: MISS – No server detected at this node."
            color = discord.Color.dark_grey()
        elif result == "hit":
            log = f"[EXPLOIT → {target}]: HIT – Server integrity compromised!"
            color = discord.Color.orange()
        elif result == "sunk":
            log = f"[EXPLOIT → {target}]: CRITICAL HIT – {ship.name} (len {ship.length}) DESTROYED! 💀"
            color = discord.Color.red()
        else:
            log = f"[EXPLOIT → {target}]: {result}"
            color = discord.Color.dark_grey()

        # Show updated boards to the channel
        attacker_board = session.boards[attacker_id]
        embed_report = discord.Embed(
            title="⚔️ EXPLOIT REPORT",
            description=f"```\n{log}\n```",
            color=color,
        )
        # Show defender's board (with hits visible) and attacker's tracking view
        embed_report.add_field(
            name="Target's Network (revealed hits)",
            value=render_grid_text(defender_board.render_reveal()),
            inline=False,
        )
        await session.channel.send(embed=embed_report)

        # Check win
        if defender_board.all_sunk:
            session.phase = "finished"
            self.active_games.pop(session.channel.id, None)
            await self._finish_game(session, attacker_id)
            return

        # Switch turn
        session.switch_turn()

        # Bot's turn
        if session.is_bot and session.turn == 0:
            await asyncio.sleep(1.5)
            await self._bot_turn(session)
            return

        # Announce next turn with a new battle view
        if session.turn == session.player1.id:
            next_name = session.player1.display_name
        else:
            next_name = session.player2.display_name if session.player2 else "???"

        view = BattleView(self, session)
        msg = await session.channel.send(
            f"⏳ **{next_name}** — your turn to attack!", view=view,
        )
        view.message = msg

    async def _bot_turn(self, session: GameSession):
        """Bot makes a random valid attack."""
        player_board = session.boards[session.player1.id]
        # Pick a random untargeted cell
        available = [
            (r, c)
            for r in range(GRID_SIZE)
            for c in range(GRID_SIZE)
            if player_board.shots[r][c] is None
        ]
        if not available:
            return
        row, col = random.choice(available)

        result, ship = player_board.receive_attack(row, col)
        target = coord_label(row, col)
        session.last_activity = time.time()

        if result == "miss":
            log = f"[🤖 BOT → {target}]: MISS"
            color = discord.Color.dark_grey()
        elif result == "hit":
            log = f"[🤖 BOT → {target}]: HIT – Your server was compromised!"
            color = discord.Color.orange()
        elif result == "sunk":
            log = f"[🤖 BOT → {target}]: CRITICAL – Your {ship.name} was DESTROYED! 💀"
            color = discord.Color.red()
        else:
            log = f"[🤖 BOT → {target}]: {result}"
            color = discord.Color.dark_grey()

        # Show the bot's attack with updated board
        embed = discord.Embed(
            title="🤖 BOT EXPLOIT REPORT",
            description=f"```\n{log}\n```",
            color=color,
        )
        embed.add_field(
            name=f"{session.player1.display_name}'s Network (damage taken)",
            value=render_grid_text(player_board.render_own()),
            inline=False,
        )
        await session.channel.send(embed=embed)

        # Check if bot won
        if player_board.all_sunk:
            session.phase = "finished"
            self.active_games.pop(session.channel.id, None)
            await self._finish_game(session, 0)
            return

        # Switch back to player
        session.switch_turn()
        view = BattleView(self, session)
        msg = await session.channel.send(
            f"⏳ **{session.player1.display_name}** — your turn to attack!", view=view,
        )
        view.message = msg

    async def _finish_game(self, session: GameSession, winner_id: int, surrendered: bool = False, timeout: bool = False):
        """Record stats, Elo, economy, reveal both boards, and announce the winner."""
        loser_id = session.opponent_id(winner_id)
        is_bot_winner = winner_id == 0
        is_bot_loser = loser_id == 0

        guild = session.channel.guild
        currency_name = "credits"
        try:
            currency_name = await bank.get_currency_name(guild)
        except Exception:
            pass

        # --- Elo & stats (skip bot) ---
        if not is_bot_winner:
            async with self.config.user_from_id(winner_id).all() as winner_data:
                w_elo = winner_data.get("elo", 1200.0)
                winner_data["wins"] = winner_data.get("wins", 0) + 1
                if not is_bot_loser:
                    async with self.config.user_from_id(loser_id).all() as loser_data:
                        l_elo = loser_data.get("elo", 1200.0)
                        new_w, new_l = elo_update(w_elo, l_elo, True)
                        winner_data["elo"] = new_w
                        loser_data["elo"] = new_l
                        loser_data["losses"] = loser_data.get("losses", 0) + 1
                else:
                    # vs bot: small Elo bump
                    winner_data["elo"] = w_elo + ELO_K * 0.25

        if not is_bot_loser and is_bot_winner:
            async with self.config.user_from_id(loser_id).all() as loser_data:
                loser_data["losses"] = loser_data.get("losses", 0) + 1
                l_elo = loser_data.get("elo", 1200.0)
                loser_data["elo"] = l_elo - ELO_K * 0.25

        # --- Economy ---
        pot = session.bet * (2 if not session.is_bot else 1)
        fee = int(pot * HOUSE_FEE_PERCENT / 100)
        payout = pot - fee + WIN_REWARD
        eco_log = ""

        if not is_bot_winner:
            try:
                winner_member = session.player1 if winner_id == session.player1.id else session.player2
                if winner_member:
                    await bank.deposit_credits(winner_member, payout)
                    eco_log = f"\n[ECO]: {winner_member.display_name} received {payout} {currency_name} (reward {WIN_REWARD} + pot {pot - fee})"
            except Exception:
                pass
        elif session.bet > 0 and not is_bot_loser:
            # Bot won — refund the human's bet
            try:
                loser_member = session.player1 if loser_id == session.player1.id else session.player2
                if loser_member:
                    await bank.deposit_credits(loser_member, session.bet)
                    eco_log = f"\n[ECO]: Bet refunded to {loser_member.display_name} (bot won)"
            except Exception:
                pass

        # --- Reveal both boards ---
        p1_board = session.boards[session.player1.id]
        p1_name = session.player1.display_name

        reveal_embed = discord.Embed(
            title="📡 FINAL BOARD REVEAL",
            description="Both networks fully decrypted:",
            color=discord.Color.gold(),
        )
        reveal_embed.add_field(
            name=f"🛡️ {p1_name}'s Network",
            value=render_grid_text(p1_board.render_reveal()),
            inline=False,
        )

        if session.is_bot:
            bot_board = session.boards[0]
            reveal_embed.add_field(
                name="🤖 Bot AI's Network",
                value=render_grid_text(bot_board.render_reveal()),
                inline=False,
            )
        elif session.player2:
            p2_board = session.boards[session.player2.id]
            p2_name = session.player2.display_name
            reveal_embed.add_field(
                name=f"🛡️ {p2_name}'s Network",
                value=render_grid_text(p2_board.render_reveal()),
                inline=False,
            )
        await session.channel.send(embed=reveal_embed)

        # --- Announce winner ---
        if is_bot_winner:
            winner_name = "🤖 Bot AI"
        else:
            try:
                w_user = await self.bot.fetch_user(winner_id)
                winner_name = w_user.display_name
            except Exception:
                winner_name = f"User {winner_id}"

        reason = ""
        if surrendered:
            reason = " (opponent surrendered)"
        elif timeout:
            reason = " (opponent timed out)"

        embed = discord.Embed(
            title="🏆 MATCH COMPLETE",
            description=(
                f"```\n"
                f"[WINNER]: {winner_name}{reason}\n"
                f"[REWARD]: {payout} {currency_name}{eco_log}\n"
                f"```"
            ),
            color=discord.Color.gold(),
        )
        await session.channel.send(embed=embed)
