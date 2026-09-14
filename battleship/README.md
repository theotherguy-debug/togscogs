# Hacking Battleship

A hacking-themed Battleship game cog for Red-DiscordBot.

## Features
- **PvP** – Challenge another user to a head-to-head match.
- **PvE** – Play against a random-attack bot AI.
- **10×10 grid** with classic ship types (hacking-themed names).
- **Interactive UI** – Button-based ship placement and attack modals via `discord.ui`.
- **Real Elo ratings** – Standard Elo formula (K=32) tracks competitive ranking.
- **Wins / Losses** leaderboard.
- **Economy integration** – Flat credit reward for wins + optional betting via Red's built-in bank.
- **Auto-place** – Quickly randomise ship positions for fast games.

## Commands

| Command | Description |
|---|---|
| `battleship [@user\|bot] [bet]` | Start a new match. Omit opponent or say `bot` for AI. |
| `bsplace <coord> <H\|V>` | Place your next ship (e.g. `bsplace A1 H`). |
| `bsattack <coord>` | Fire an exploit at a coordinate (e.g. `bsattack E5`). |
| `bsboard` | View your board and enemy fog-of-war. |
| `bscancel` | Cancel the current game and refund bets. |
| `bsleaderboard` | Show the Elo-ranked leaderboard. |

## Installation

```
[p]load battleship
```

## Ships

| Name | Length |
|---|---|
| Mainframe | 5 |
| Firewall | 4 |
| Proxy | 3 |
| Rootkit | 3 |
| Exploit | 2 |
