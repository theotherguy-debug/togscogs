# -*- coding: utf-8 -*-
"""Configuration constants for the Hacking Battleship cog.
All values can be overridden via Red‑DiscordBot's cog settings if desired.
"""

# Board dimensions (standard Battleship)
GRID_SIZE = 10

# Ship definitions: name -> length
# Classic ships, you can rename them for a hacking theme if you wish.
SHIP_DEFS = {
    "Carrier": 5,
    "Battleship": 4,
    "Cruiser": 3,
    "Submarine": 3,
    "Destroyer": 2,
}

# Turn timeout in seconds (2 minutes)
TURN_TIMEOUT = 120

# Elo calculation factor
ELO_K = 32

# Fixed reward for a win (credits)
WIN_REWARD = 100

# Default bet amount (0 = no bet)
DEFAULT_BET = 0

# House fee percentage taken from each pot (0 = none)
HOUSE_FEE_PERCENT = 0
