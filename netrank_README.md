# NetRank — XP & Leveling System Documentation

## Table of Contents
1. [Overview](#overview)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Commands](#commands)
5. [Level System](#level-system)
6. [XP Sources](#xp-sources)
7. [Rank Tiers](#rank-tiers)
8. [Event Architecture](#event-architecture)
9. [UI Integration](#ui-integration)
10. [Troubleshooting](#troubleshooting)

---

## Overview

NetRank is a server-wide cybersecurity-themed experience (XP) and leveling system for Discord bots built on Red-DiscordBot. It provides:

- **Automated XP tracking** across multiple activity sources
- **Level progression** with custom formulas and tier-based rank titles
- **Role rewards** automatically assigned at level thresholds
- **Event-driven architecture** that hooks into NetCount counting events
- **Admin control panel** integration via the `/root` mainframe UI
- **Customizable broadcast channels** for level-up announcements

### Key Features

- **No direct dependencies** on other cogs (uses event listeners)
- **Progressive XP multipliers** based on streak depth
- **Flexible XP source configuration** (enable/disable per source)
- **Contribution-based rewards** for survivor milestones
- **Anti-spam cooldowns** for message-based XP
- **ANSI-styled embeds** for cyberpunk aesthetic

---

## Installation

### Prerequisites

- Red-DiscordBot v3.5.0 or higher
- NetCount cog (recommended for full integration)
- Bank/Economy cog (optional, for economy features)

### Steps

1. **Copy the cog files** to your Red bot's cogs directory:
   ```
   Togscogs/netrank/
   ├── __init__.py
   ├── netrank.py
   ├── info.json
   └── README.md
   ```

2. **Load the cogs** in order:
   ```bash
   [p]load netcount
   [p]load netrank
   ```

3. **Verify installation**:
   ```bash
   [p]cogs
   ```
   You should see `netrank` listed as loaded.

### Cog Identifier

- **Name**: `netrank`
- **Author**: Th3OTh3rGuy
- **Config ID**: `8923487319`

---

## Configuration

### Guild-Level Settings

NetRank stores guild-specific configuration in Red's Config system. Default values:

```python
{
    "xp_sources": {
        "counts": True,      # XP from valid counting messages
        "duels": True,       # XP from duel wins (no wager only)
        "survivor": True,    # XP from survivor milestones
        "messages": False,   # XP from general messages (off by default)
        "voice": True        # XP from voice channel activity
    },
    "xp_per_count": 10,
    "xp_per_duel_win": 250,
    "xp_per_survivor_milestone": 500,
    "xp_per_message": 5,
    "message_xp_cooldown": 60,
    "xp_per_voice_minute": 2,     # XP awarded per minute in VC
    "voice_xp_interval": 60,      # How often to check (seconds)
    "voice_min_members": 2,       # Minimum members needed
    "level_up_channel_id": None,
    "level_roles": {},            # str(level) -> role_id mapping
    "rank_enabled": True          # Master toggle for ranking system
}
```

### Member-Level Settings

Each member has persistent data:

```python
{
    "xp": 0,                      # Total accumulated XP
    "level": 0,                   # Current calculated level
    "last_message_xp_time": 0.0   # Timestamp of last message XP
}
```

### Configuration Methods

#### Via Commands

```bash
# Toggle ranking system
[p]ranking toggle

# Set XP per source
[p]ranking setxp <source> <amount>
# Examples:
[p]ranking setxp counts 15
[p]ranking setxp duels 300
[p]ranking setxp survivor 750
[p]ranking setxp messages 3
[p]ranking setxp voice 3

# Set level-up broadcast channel
[p]ranking levelchannel [channel]
# Leave empty to clear

# Add level role
[p]ranking roleadd <level> <role>
# Example:
[p]ranking roleadd 10 @CyberTechnician

# Remove level role
[p]ranking roleremove <level>

# Manual XP control
[p]ranking givexp <member> <amount>
[p]ranking resetxp <member>
[p]ranking resetall
```

#### Via UI Panel

1. Run `[p]root` to open the Mainframe Admin Control Panel
2. Click **"Ranking System"** button
3. Use the interactive buttons and modals to configure settings

---

## Commands

### User Commands

#### `[p]rank [member]`
**Aliases**: `level`, `xp`

Display an operative's profile card with ANSI-styled formatting.

**Features**:
- Current level and tier name
- XP progress bar (20 characters)
- Global server rank
- Next level XP requirement

**Example Output**:
```
╔══════════════════════════════════════════════════════╗
║               SYSTEM OPERATIVE DOS: 4.1              ║
╚══════════════════════════════════════════════════════╝

 OPERATIVE:   UserName#1234
 ACCESS LVL:  15 [Security Analyst]
 GLOBAL RANK: #3 / 45

 SYSTEM INDEX PROGRESSION:
 XP: 14,378 / 24,458 [58.8%]
 [███████████████░░░░░░░░░░░░░░░░░░░░]
```

#### `[p]ranktop`
**Aliases**: `leveltop`, `ltop`

Display the top 10 operatives ranked by XP.

**Features**:
- Styled ANSI leaderboard
- Rank numbers with color coding (gold/silver/bronze)
- Level and XP display
- Padded name columns for alignment

---

### Admin Commands

All admin commands are under the `[p]ranking` group.

#### `[p]ranking toggle`
Toggle the entire ranking system on/off.

**Example**:
```bash
[p]ranking toggle
# Output: ✅ Mainframe ranking matrix is now ONLINE.
```

#### `[p]ranking setxp <source> <amount>`
Configure XP rewards per source.

**Valid Sources**:
- `counts` - XP from counting messages
- `duels` - XP from duel wins
- `survivor` - XP from survivor milestones
- `messages` - XP from general messages
- `voice` - XP from voice channel activity

**Example**:
```bash
[p]ranking setxp counts 20
# Output: ✅ Successfully updated reward parameter. counts now grants 20 XP.
```

#### `[p]ranking levelchannel [channel]`
Set or clear the level-up broadcast channel.

**Example**:
```bash
[p]ranking levelchannel #level-ups
# Output: ✅ Level-up alerts will now be routed to #level-ups.

[p]ranking levelchannel
# Output: ✅ Level-up broadcast channel cleared.
```

#### `[p]ranking roleadd <level> <role>`
Map a Discord role to a specific level.

**Example**:
```bash
[p]ranking roleadd 25 @EliteOperator
# Output: 🏆 Role reward configured: Reaching level 25 will award @EliteOperator.
```

#### `[p]ranking roleremove <level>`
Remove a level-to-role mapping.

**Example**:
```bash
[p]ranking roleremove 25
# Output: ✅ Removed level 25 role reward.
```

#### `[p]ranking givexp <member> <amount>`
Manually award XP to a member.

**Example**:
```bash
[p]ranking givexp @User 500
# Output: ⚡ Injected 500 XP into operative @User's registry buffer.
```

#### `[p]ranking resetxp <member>`
Reset a member's XP and level to 0.

**Example**:
```bash
[p]ranking resetxp @User
# Output: 🧹 Realigned registry buffer. Operative @User's XP and level have been reset to 0.
```

#### `[p]ranking resetall`
Wipe all XP and level data for the entire guild.

**Example**:
```bash
[p]ranking resetall
# Output: 🚨 DATABASE PURGED: Cleared all operative levels and XP registry records from this guild.
```

---

## Level System

### XP Formula

The XP required to unlock level **N** is calculated as:

```
XP(N) = floor(150 × N^1.7)
```

This creates a moderately challenging progression curve that accelerates but remains achievable.

### Level Calculation

NetRank uses binary search to efficiently determine a member's level from their total XP:

```python
def get_level_from_xp(self, xp: int) -> int:
    low = 1
    high = 500  # Reasonable cap
    current_lvl = 0
    
    while low <= high:
        mid = (low + high) // 2
        if xp_for_level(mid) <= xp:
            current_lvl = mid
            low = mid + 1
        else:
            high = mid - 1
    return current_lvl
```

### Level-Up Process

When a member crosses a level threshold:

1. **Database Update**: Member's `level` field is updated
2. **Role Assignment**: If a role is mapped to the new level, it's added
3. **Broadcast Announcement**: Sent to configured level-up channel (if set)
4. **Local Notification**: Temporary embed posted where XP was earned (auto-deletes after 10 minutes)

**Note**: Level-up announcements are dispatched as background tasks to avoid blocking the XP award flow.

---

## XP Sources

### 1. Valid Counts

**Default XP**: 10 × streak multiplier

**Streak Multiplier**:
- Counts 1-99: 1×
- Counts 100-199: 2×
- Counts 200-299: 3×
- And so on...

**Trigger**: Event `on_netcount_valid_count`

**Example**:
- Count 50: 10 × 1 = **10 XP**
- Count 150: 10 × 2 = **20 XP**
- Count 350: 10 × 4 = **40 XP**

### 2. Duel Wins

**Default XP**: 250 (flat)

**Conditions**: Only awarded when wager = 0 (no economy exploit)

**Trigger**: Event `on_netcount_duel_complete`

**Note**: Duels with wagers do not grant XP to prevent farming.

### 3. Survivor Milestones

**Default XP Pool**: 500 (split proportionally)

**Distribution**: XP is split among contributors based on their count contributions.

**Trigger**: Event `on_netcount_survivor_milestone`

**Example**:
- Total milestone XP: 500
- Player A contributed 60 counts
- Player B contributed 40 counts
- Player A receives: 500 × (60/100) = **300 XP**
- Player B receives: 500 × (40/100) = **200 XP**

### 4. General Messages

**Default XP**: 5 per message

**Cooldown**: 60 seconds (configurable)

**Conditions**:
- Disabled by default
- Only active in non-counting channels
- Subject to anti-spam cooldown per member

**Trigger**: Event `on_message`

### 5. Voice Channel Activity

**Default XP**: 2 per minute

**Conditions**:
- Enabled by default
- Requires minimum 2 non-bot members in channel (no solo XP)
- AFK channels excluded
- 60-second cooldown between awards

**Configuration**:
- `xp_per_voice_minute`: XP awarded per minute (default: 2)
- `voice_min_members`: Minimum members required (default: 2)
- `voice_xp_interval`: How often to check/award (default: 60 seconds)

**Trigger**: Background task `voice_xp_checker` (runs every 60 seconds)

**Example**:
- User spends 5 minutes in voice channel with 3 others: 5 × 2 = **10 XP**
- User alone in VC: **0 XP** (minimum members not met)
- User in AFK channel: **0 XP** (excluded)

**Anti-Abuse Features**:
- Prevents solo AFK farming
- Requires actual social interaction
- Low XP rate prevents grinding
- Cooldown prevents exploit loops

---

## Rank Tiers

Operatives are assigned tier names based on their level:

| Level Range | Tier Name |
|:---:|:---|
| 0–4 | Script Kiddie |
| 5–9 | Novice Operator |
| 10–14 | Field Technician |
| 15–19 | Security Analyst |
| 20–29 | Network Infiltrator |
| 30–39 | Cyber Architect |
| 40–49 | Shadow Protocol |
| 50–74 | Ghost in the Shell |
| 75–99 | System Administrator |
| 100+ | ROOT ACCESS |

**Implementation**:
```python
def get_rank_tier(self, level: int) -> str:
    if level < 5:
        return "Script Kiddie"
    elif level < 10:
        return "Novice Operator"
    # ... etc
```

---

## Event Architecture

NetRank uses a **decoupled event-driven design** — it does not import NetCount directly. Instead, it listens for custom events dispatched by NetCount.

### Events Dispatched by NetCount

#### `on_netcount_valid_count`
Dispatched after a valid counting message.

**Payload**:
- `message`: The Discord message object
- `expected_number`: The count value that was validated

**Usage in NetRank**:
- Awards XP based on streak multiplier
- Triggers level-up check

#### `on_netcount_duel_complete`
Dispatched when a counting duel ends.

**Payload**:
- `guild`: The Discord guild
- `winner`: The winning member
- `loser`: The losing member
- `wager`: The wager amount (0 if no economy)
- `final_count`: The last count reached in the duel

**Usage in NetRank**:
- Awards flat XP to winner (if wager = 0)
- No XP if economy was involved

#### `on_netcount_survivor_milestone`
Dispatched when a survivor channel milestone is reached.

**Payload**:
- `guild`: The Discord guild
- `milestone`: The milestone number reached
- `contributors`: Dict of `{user_id: contribution_count}`

**Usage in NetRank**:
- Distributes milestone XP pool proportionally
- Triggers level-up checks for all contributors

### Event Listener Pattern

```python
@commands.Cog.listener()
async def on_netcount_valid_count(self, message: discord.Message, expected_number: int):
    # Award XP logic here
    await self.add_xp(message.author, xp_to_award, message.channel)
```

**Benefits**:
- NetRank can be unloaded without breaking NetCount
- Other cogs can dispatch the same events
- Easy to extend with new XP sources

---

## UI Integration

NetRank is fully integrated into the Red-DiscordBot's `/root` mainframe control panel.

### Accessing the Panel

1. Run `[p]root` in any server channel
2. Click the **"Ranking System"** button (⚡ emoji)
3. The `RankingSubsystemView` will load

### Available UI Controls

#### Buttons

| Button | Action |
|:---|:---|
| **Toggle System** | Enable/disable ranking globally |
| **Set Level Channel** | Set broadcast channel via modal |
| **Clear Level Channel** | Remove broadcast channel |
| **Configure XP / Sources** | Modal to set XP values and toggle sources |
| **Add Level Role** | Modal to add level→role mapping |
| **Remove Level Role** | Modal to remove level→role mapping |
| **Operative Control** | Modal for givexp/reset actions |
| **Main Menu** | Return to root panel |

### Modals

#### RankingConfigureXPModal
Configure all XP parameters in one form:
- Base XP per count
- XP per duel win
- XP per survivor milestone
- XP per message + cooldown
- Enable/disable sources (comma-separated)

#### RankingAddRoleModal
Add a level role reward:
- Target level
- Role name or ID

#### RankingRemoveRoleModal
Remove a level role reward:
- Target level

#### RankingOperativeControlModal
Perform member-level actions:
- User ID or username
- Action: `givexp` or `reset`
- Amount (for givexp)

### Code Reference

The UI implementation is located in:
- **File**: `Togscogs/root/root.py`
- **Class**: `RankingSubsystemView` (lines 1210–1284)
- **Modals**: Lines 1301–1434

---

## Troubleshooting

### Common Issues

#### 1. XP Not Awarded

**Check**:
- Is NetCount loaded? (Events come from NetCount)
- Is ranking enabled? `[p]ranking toggle` → should be ONLINE
- Are XP sources enabled? Check guild config for `xp_sources`
- Is the member a bot? (Bots don't earn XP)

**Debug**:
```bash
[p]ranking toggle  # Verify it's ON
[p]ranking setxp counts 10  # Verify XP value
```

#### 2. Level-Up Not Announcing

**Check**:
- Is a level-up channel configured? `[p]ranking levelchannel`
- Does the bot have permission to send embeds in that channel?
- Is the channel ID valid?

**Fix**:
```bash
[p]ranking levelchannel #your-announcement-channel
```

#### 3. Roles Not Assigning

**Check**:
- Is the role hierarchy correct? Bot's role must be higher than the reward role.
- Does the bot have `Manage Roles` permission?
- Is the level role configured? `[p]ranking roleadd <level> <role>`

**Fix**:
- Move bot's role above reward roles in server settings
- Grant `Manage Roles` permission to bot

#### 4. Message XP Not Working

**Check**:
- Is `messages` source enabled?
  ```bash
  [p]ranking setxp messages 5
  ```
- Is the channel a counting channel? (Message XP is disabled in counting channels to avoid double-rewarding)
- Has the cooldown expired? (Default: 60 seconds)

#### 5. Duel XP Not Awarded

**Check**:
- Was the wager > 0? (No XP for gambling duels)
- Is the `duels` source enabled?
  ```bash
  [p]ranking setxp duels 250
  ```

### Logging

NetRank does not include explicit logging. For debugging:

1. Check Red bot console for error traces
2. Verify event dispatch in NetCount logs
3. Use `[p]debug` to inspect cog states

### Resetting Data

If configuration becomes corrupted:

```bash
# Reset single member
[p]ranking resetxp @User

# Reset entire guild
[p]ranking resetall

# Toggle system off/on to refresh
[p]ranking toggle
[p]ranking toggle
```

---

## Advanced Topics

### Custom XP Formulas

To modify the XP formula, edit the `add_xp` method in `netrank.py`:

```python
# Default: flat XP
xp_to_award = base_xp * multiplier

# Custom: exponential scaling
xp_to_award = int(base_xp * (multiplier ** 1.5))
```

### Custom Level Curves

Modify `xp_for_level` to change progression:

```python
# Default: 150 * level^1.7
def xp_for_level(self, level: int) -> int:
    return int(150 * (level ** 1.7))

# Steeper curve example:
def xp_for_level(self, level: int) -> int:
    return int(200 * (level ** 2.0))
```

### Adding New XP Sources

1. Dispatch a new event from your cog:
   ```python
   self.bot.dispatch("custom_xp_event", member, amount)
   ```

2. Add listener in NetRank:
   ```python
   @commands.Cog.listener()
   async def on_custom_xp_event(self, member, amount):
       await self.add_xp(member, amount, None)
   ```

### Performance Considerations

- **Binary search** for level calculation: O(log n) complexity
- **Background tasks** for level-ups prevent blocking
- **Config caching**: Red's Config handles efficient data retrieval
- **Member lookups**: Limited to top 10 for leaderboards

### Database Schema

NetRank uses Red's Config system with three namespaces:

1. **Guild Config**: `NetRank.__identifier__`
   - Key: `guild:<guild_id>`
   - Stores global settings

2. **Member Config**: `NetRank.__identifier__`
   - Key: `member:<guild_id>:<member_id>`
   - Stores per-member XP data

3. **No global config**: All data is scoped to guilds

---

## API Reference

### Core Methods

#### `add_xp(member, amount, channel)`
Add XP to a member and trigger level-up if threshold crossed.

**Parameters**:
- `member` (discord.Member): Target member
- `amount` (int): XP to add
- `channel` (discord.TextChannel, optional): Channel for local notification

**Returns**: None

**Side Effects**:
- Updates member XP in database
- Triggers `handle_level_up` if level increased
- Sends announcements

#### `get_level_from_xp(xp)`
Calculate the level corresponding to a total XP value.

**Parameters**:
- `xp` (int): Total accumulated XP

**Returns**: int (current level)

#### `xp_for_level(level)`
Calculate the absolute XP required to unlock a level.

**Parameters**:
- `level` (int): Target level (must be > 0)

**Returns**: int (XP required)

#### `get_rank_tier(level)`
Get the cybersecurity tier name for a level.

**Parameters**:
- `level` (int): Current level

**Returns**: str (tier name)

### Event Handlers

All event handlers are decorated with `@commands.Cog.listener()`:

- `on_netcount_valid_count(message, expected_number)`
- `on_netcount_duel_complete(guild, winner, loser, wager, final_count)`
- `on_netcount_survivor_milestone(guild, milestone, contributors)`
- `on_message(message)` — for message XP

---

## Changelog

### Version 1.0.0 (Current)

- Initial release
- Full XP and leveling system
- Event-driven integration with NetCount
- UI integration with `/root` panel
- Five XP sources (counts, duels, survivor, messages, voice)
- Role reward system
- Broadcast and local level-up announcements
- Admin command suite
- ANSI-styled embeds

### Version 1.1.0 (Voice XP Update)

- Added voice channel XP system
- Requires minimum 2 members to prevent solo farming
- AFK channel exclusion
- Configurable XP rate and minimum members
- Background task for automatic awards

---

## Support

For issues, feature requests, or contributions:
- **Author**: Th3OTh3rGuy
- **Repository**: Togscogs/netrank
- **Related Cogs**: NetCount, Root, SysNames, Hijack, Purge, Vital

---

## License

See the parent Togscogs repository for license information.