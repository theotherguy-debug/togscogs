# Purge — AutoClean Channel Manager

Automated message clean-up system with configurable per-channel deletion delays, user/role whitelists, and on-demand bulk purges. Keeps command channels, temporary channels, and bot-response channels clean.

---

## 🚀 Setup & Installation

1. Load the cog:
   ```
   [p]load purge
   ```
2. Designate channels for auto-cleanup:
   - **GUI**: Open `/root` → **AutoClean** → select a channel → **Toggle Clean**
   - **Text**: `[p]autoclean channel <channel>`

---

## ⌨️ Admin Commands

| Command | Description |
|:---|:---|
| `[p]autoclean channel <channel>` | Toggle AutoClean on/off for a specific channel |
| `[p]autoclean delay <channel> <seconds>` | Set how long messages live before automatic deletion |

---

## 🛠️ Admin Controls (via `/root` → AutoClean)

| Button | Description |
|:---|:---|
| **Toggle Clean** | Enable/disable AutoClean on the selected channel |
| **Set Deletion Delay** | Configure the number of seconds before messages are auto-deleted (default: 3600s) |
| **Purge Messages Now** | Immediately bulk-delete up to 2,000 messages from the selected channel |
| **Whitelist User** | Toggle a specific user's immunity from AutoClean deletions |
| **Whitelist Role** | Toggle a role's immunity from AutoClean deletions |

---

## 🔧 How It Works

1. When enabled on a channel, every new message starts a deletion timer
2. After the configured delay, the message is automatically deleted
3. Messages from whitelisted users or members with whitelisted roles are preserved
4. Admins can trigger immediate bulk purges for quick clean-up
