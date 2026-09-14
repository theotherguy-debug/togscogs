# SysNames — Nickname Format Themes

A cyberpunk-themed automated nickname formatter. Modifies member nicknames server-wide or on-join to match specific code script aesthetics. Choose from terminal, virus, database, system, and network themes — or randomise.

---

## 🚀 Setup & Installation

1. Load the cog:
   ```
   [p]load sysnames
   ```
2. Configure themes:
   - **GUI**: Open `/root` → **Nicknames** → select a theme from the dropdown
   - **Text**: `[p]sysnames theme <theme>`
3. Enable auto-formatting on member join:
   - **GUI**: `/root` → **Nicknames** → **Toggle Auto-Format**
   - **Text**: `[p]sysnames toggle`

---

## 🎨 Available Themes

| Theme | Example Output | Style |
|:---|:---|:---|
| `terminal` | `username.py` | Python script |
| `virus` | `username.exe` | Windows executable |
| `database` | `db_username` | Database table prefix |
| `system` | `systemd-username` | Linux systemd service |
| `network` | `ip_username` | Network protocol prefix |
| `all` | Random per user | Randomly assigns one of the above |

---

## ⌨️ Admin Commands

| Command | Description |
|:---|:---|
| `[p]sysnames theme <theme>` | Change the active naming theme server-wide |
| `[p]sysnames toggle` | Turn join auto-formatting on or off |

---

## 🛠️ Admin Controls (via `/root` → Nicknames)

| Button | Description |
|:---|:---|
| **Theme Dropdown** | Select from terminal, virus, database, system, network, or random themes |
| **Toggle Auto-Format** | Enable/disable automatic nickname formatting when new members join |
| **Format All Members** | Apply the current theme to every non-bot member in the server |
| **Format Specific User** | Format a single user's nickname by entering their ID or username |
| **Reset All Nicknames** | Strip all theme formatting from every member, restoring original names |

---

## ⚠️ Requirements

- Bot must have `Manage Nicknames` permission
- Bot's role must be **higher** than the target user's highest role in the role hierarchy
- Server owner nicknames cannot be changed by the bot (Discord limitation)
