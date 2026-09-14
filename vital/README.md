# Vital — Wellbeing Alerts

Periodically broadcasts randomised wellbeing reminders, healthy tips, and mental wellness checks to configured channels. Designed to keep operatives balanced during long gaming and moderation sessions. Alerts are styled in ANSI terminal format and self-delete to keep channels clean.

---

## 🚀 Setup & Installation

1. Load the cog:
   ```
   [p]load vital
   ```
2. Add alert channels:
   - **GUI**: Open `/root` → **Wellbeing Alerts** → select a channel → **Add Alert Channel**
   - **Text**: `[p]vital add <channel>`
3. Optionally configure timing:
   - **GUI**: `/root` → **Wellbeing Alerts** → **Set Broadcast Interval**
   - **Text**: `[p]vital interval <min_hours> <max_hours>`

---

## ⌨️ Admin Commands

| Command | Description |
|:---|:---|
| `[p]vital add <channel>` | Add a channel to receive randomised wellbeing broadcasts |
| `[p]vital interval <min_hours> <max_hours>` | Set bounds for randomised alert timing (default: 3–6 hours) |

---

## 🛠️ Admin Controls (via `/root` → Wellbeing Alerts)

| Button | Description |
|:---|:---|
| **Add Alert Channel** | Register the selected channel to receive wellbeing broadcasts |
| **Remove Alert Channel** | Unregister a channel from broadcasts |
| **Set Broadcast Interval** | Configure minimum and maximum hours between random alerts |
| **Broadcast Test Alert** | Send a single test alert to the selected channel (self-deletes in 5 minutes) |

---

## 🔧 How It Works

1. The cog maintains a pool of built-in wellness alerts (loaded from `alerts.json`) plus any custom alerts added by admins
2. At random intervals within the configured bounds, it selects a random alert and broadcasts it
3. Alerts are formatted in ANSI terminal styling to match the cyberpunk aesthetic
4. A history buffer prevents the same alert from appearing back-to-back
