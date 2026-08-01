# Root — Mainframe Operator Panel

The centralised admin command dashboard for the Togscogs suite. One slash command opens a fully interactive button-driven GUI to control every gaming, moderation, economy, and utility subsystem.

---

## 🚀 Setup & Installation

1. Register the cog path (if not already done):
   ```
   [p]addpath C:\Users\andre\OneDrive\Desktop\Togscogs
   ```
2. Load the cog:
   ```
   [p]load root
   ```
3. Open the mainframe panel:
   ```
   [p]root
   ```

> [!NOTE]
> Load all other cogs **before** loading Root so the panel detects every subsystem.

---

## 🎛️ Main Panel Layout

| Button | Emoji | Row | Subsystem Controlled |
|:---|:---|:---|:---|
| Counting System | 🔢 | 1 | NetCount — toggle channels, wagers, saves, survivor mode, prestige |
| Nicknames | 🏷️ | 1 | SysNames — select themes, format all/individual users, reset |
| Hacking UI | 👾 | 1 | Hijack — toggle firewall lockdown |
| AutoClean | 🧹 | 2 | Purge — channel cleanup, delay timers, whitelists |
| Wellbeing Alerts | 🏥 | 2 | Vital — broadcast channels, intervals, test alerts |
| Ranking System | ⚡ | 2 | NetRank — XP sources, level roles, operative DB control |
| Economy & Bank | 💰 | 3 | Red economy — default balances, payday config |
| Broadcast DM | 🚨 | 3 | Mass DM to all members or specific roles |
| Exit Matrix | ❌ | 3 | Close and lock the mainframe session |

---

## 🔒 Access Control

- **Admin only**: Requires `manage_guild` permission or Red admin role.
- **Author locked**: Only the admin who opened `/root` can interact with the buttons. Other users are rejected with a terminal error.
- **Auto-timeout**: The panel auto-expires after 5 minutes of inactivity.

---

## ⚡ Ranking System Panel

Within the Ranking subsystem, the following controls are available:

| Control | Description |
|:---|:---|
| **Toggle System** | Enable/disable the entire XP and leveling system |
| **Set Level Channel** | Choose which channel receives level-up announcements |
| **Clear Level Channel** | Remove the broadcast channel (notifications go local only) |
| **Configure XP / Sources** | Set XP per count/duel/survivor/message, toggle sources, set cooldowns |
| **Add Level Role** | Map a Discord role to a specific level (auto-assigned on level-up) |
| **Remove Level Role** | Delete a level → role mapping |
| **Operative Control** | Inject XP or reset a specific member's level data |

---

## 💰 Economy Panel

| Control | Description |
|:---|:---|
| **Set Default Balance** | Change the starting credit balance for new members |
| **Set All Balances** | Override every member's bank balance (destructive) |
| **Configure Payday** | Set the credit amount and cooldown for `[p]payday` |

---

## 🚨 Broadcast DM

Opens a popup modal where you specify:
- **Target**: `all` for every non-bot member, or a role name
- **Message**: The content to DM

Messages are sent with a 1.5s delay between each to avoid Discord rate limits. A summary report is DM'd to the admin upon completion showing success/fail counts.
