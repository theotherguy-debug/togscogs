# NetRank — XP & Leveling System

A server-wide cybersecurity-themed experience (XP) and leveling system. Hooks into counting events from NetCount, rewards active operatives, grants milestone roles, and announces rank changes with styled ANSI terminal embeds.

---

## 🚀 Setup & Installation

1. Load the cog (load `netcount` first for event integration):
   ```
   [p]load netcount
   [p]load netrank
   ```
2. Open `/root` → **Ranking System** to configure XP sources, level roles, and broadcast channels.

---

## 📈 Level Formula

$$\text{XP Required for Level } N = \lfloor 150 \times N^{1.7} \rfloor$$

The curve is calibrated to be moderately challenging — not grindy, but not trivially easy either.

### Difficulty Reference
| Level | Total XP Required | Approx. Counts Needed | Tier |
|:---:|:---:|:---:|:---|
| 1 | 150 | ~15 | Script Kiddie |
| 5 | 2,314 | ~231 | Novice Operator |
| 10 | 7,518 | ~751 | Field Technician |
| 15 | 14,378 | ~1,437 | Security Analyst |
| 20 | 24,458 | ~2,446 | Network Infiltrator |
| 30 | 50,164 | ~5,016 | Cyber Architect |
| 50 | 114,631 | ~11,463 | Shadow Protocol |
| 75 | 222,748 | ~22,274 | System Administrator |
| 100 | 376,780 | ~37,678 | ROOT ACCESS |

---

## ⚔️ XP Sources

| Source | Default XP | Conditions |
|:---|:---|:---|
| **Valid Count** | 10 × streak tier | Streak multiplier: `floor(count / 100) + 1` |
| **Duel Win** | 250 (flat) | Only when wager = 0 (no economy exploit) |
| **Survivor Milestone** | 500 (split) | Proportional to contribution count |
| **General Messages** | 5 per message | Off by default. 60s anti-spam cooldown |

All values are configurable via `/root` → Ranking System → Configure XP / Sources.

---

## 🏆 Rank Tiers

| Level Range | Tier Name |
|:---|:---|
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

---

## 💬 Level Up Behaviour

When an operative crosses a level threshold:

1. **Broadcast Channel**: If a level-up channel is configured, a permanent styled announcement embed is posted there.
2. **Local Notification**: A temporary embed appears in the channel where XP was earned. It auto-deletes after **10 minutes**.
3. **Role Rewards**: If a role is mapped to the new level, it's instantly assigned to the user.

---

## ⌨️ User Commands

| Command | Aliases | Description |
|:---|:---|:---|
| `[p]rank [member]` | `level`, `xp` | View operative profile card with ANSI progress bar, level, tier, and server rank |
| `[p]ranktop` | `leveltop`, `ltop` | View top 10 operatives on the decryption leaderboard |

---

## 🛠️ Admin Commands

| Command | Description |
|:---|:---|
| `[p]ranking toggle` | Toggle the entire ranking system on/off |
| `[p]ranking setxp <source> <amount>` | Set XP reward per source (`counts`, `duels`, `survivor`, `messages`) |
| `[p]ranking levelchannel [channel]` | Set or clear the level-up broadcast channel |
| `[p]ranking roleadd <level> <role>` | Assign a role to be auto-granted at a level |
| `[p]ranking roleremove <level>` | Remove a level → role mapping |
| `[p]ranking givexp <member> <amount>` | Manually inject XP into a user's registry buffer |
| `[p]ranking resetxp <member>` | Reset a single user's XP and level to 0 |
| `[p]ranking resetall` | Wipe all XP and level data for the entire guild |

---

## 🎛️ Admin Controls (via `/root` → Ranking System)

| Button | Description |
|:---|:---|
| **Toggle System** | Enable/disable the ranking system globally |
| **Set Level Channel** | Route level-up announcements to the selected channel |
| **Clear Level Channel** | Remove the broadcast channel (local-only notifications) |
| **Configure XP / Sources** | Edit XP amounts per source and toggle individual sources on/off |
| **Add Level Role** | Map a Discord role to a specific level number |
| **Remove Level Role** | Delete a level → role mapping |
| **Operative Control** | Inject XP or reset a specific user's data via popup modal |

---

## 🔗 Event-Driven Architecture

NetRank does **not** import or depend on NetCount directly. Instead, it listens for custom events dispatched by NetCount:

```python
# NetCount dispatches:
self.bot.dispatch("netcount_valid_count", message, expected_number)
self.bot.dispatch("netcount_duel_complete", guild, winner, loser, wager, final_count)
self.bot.dispatch("netcount_survivor_milestone", guild, milestone, contributors)

# NetRank listens:
@commands.Cog.listener()
async def on_netcount_valid_count(self, message, expected_number): ...
```

This means you can unload NetRank without affecting counting, or add future XP sources by dispatching new events from any cog.
