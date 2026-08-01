# NetCount — Sequence Counting Game

A multi-channel sequence counting game with cybersecurity elements. Features economy-linked wagers, save tokens, prestige targets, real-time 1v1 duels, and a brutal Survivor mode with license fees, bankruptcy penalties, and exile timers.

---

## 🚀 Setup & Installation

1. Load the cog:
   ```
   [p]load netcount
   ```
2. Enable counting in a channel:
   - **GUI**: Open `/root` → **Counting System** → select a channel → **Toggle Counting**
   - **Or** configure via cog-specific settings

> [!IMPORTANT]
> Load `netcount` **before** `netrank` so ranking events are dispatched correctly.

---

## 🎮 How Counting Works

Members take turns posting sequential numbers in a counting channel. Rules:
- **No double-counting**: You can't count twice in a row
- **Correct number only**: Wrong numbers break the streak (consequences depend on mode)
- **Streak multiplier**: Every 100 numbers, a bonus multiplier kicks in

### Survivor Mode
An extreme-stakes variant where:
- **Saves are disabled** — one mistake resets the count
- **License required** — users must purchase a survivor license with credits
- **Bankruptcy penalty** — the person who breaks the chain loses a percentage of their bank balance
- **Exile** — rule-breakers are temporarily banned from the survivor channel
- **Jackpot** — credits accumulate in a vault and pay out at milestones

---

## 🖼️ Milestone Images (Auto-Detection)

NetCount can automatically detect and send milestone images when a count milestone is reached — **no manual configuration needed**.

### How It Works

1. **Name your image files by the milestone number** (e.g., `100.png`, `500.jpg`, `1000.gif`)
2. **Place them in a directory** — either the default `milestones/` folder next to the cog, or a custom path
3. **The bot auto-detects them** when that count is reached and posts the image

### Supported Formats
`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`

### Priority
Manual milestones (set via `addmilestone`) take priority over auto-detected images. This lets you override specific milestones with URLs or stickers while using auto-detection for the rest.

### Commands

| Command | Description |
|:---|:---|
| `[p]counting setmilestonedir <path>` | Set a custom directory for milestone images. Leave empty to reset to default. |
| `[p]counting scanmilestones` | Scan the directory and list all detected milestone images |
| `[p]counting toggleautomilestones <true/false>` | Enable or disable auto-detection |

### Example
```
# Drop files in the default folder:
Togscogs/netcount/milestones/
├── 100.png      ← triggers at count 100
├── 500.jpg      ← triggers at count 500
└── 1000.gif     ← triggers at count 1000

# Or point to a custom folder:
[p]counting setmilestonedir C:\path\to\your\images

# Verify what's detected:
[p]counting scanmilestones
```

---

## ⌨️ User Commands

| Command | Description |
|:---|:---|
| `[p]cduel <opponent> [wager]` | Challenge another user to a real-time counting duel in a private thread. Optional credit wager. |
| `[p]buysurv` / `[p]buysurvivorlicense` | Purchase a license to participate in survivor counting rooms |
| `[p]jackpot` | View credits currently accumulated in the counting vault |

---

## 🔗 Integration with NetRank

NetCount dispatches three custom events that NetRank listens to:

| Event | When Fired | XP Effect |
|:---|:---|:---|
| `on_netcount_valid_count` | Every correct sequential count | Awards base XP × streak multiplier |
| `on_netcount_duel_complete` | When a duel ends | Awards lump-sum XP to the winner (wager=0 only) |
| `on_netcount_survivor_milestone` | When a survivor milestone is reached | Splits milestone XP among contributors |

---

## 🛠️ Admin Controls (via `/root` → Counting System)

| Button | Description |
|:---|:---|
| **Toggle Counting** | Enable/disable counting in the selected channel |
| **Toggle Survivor Mode** | Activate extreme-stakes survivor rules |
| **Toggle Saves** | Enable/disable save token usage per channel |
| **Toggle Economy** | Link counting rewards to the Red economy |
| **Set Current Count** | Manually override the current count value |
| **Give Save Token** | Award save tokens to a channel's pool |
| **Set Save Price** | Set the credit cost to purchase saves |
| **Set Prestige Target** | Set the target number for prestige resets (min 100) |
| **Survivor Rules** | Configure license fees, bankruptcy %, and exile duration |
| **Global Shaming** | Set shame nickname tags and lockout durations |
| **Pardon Member** | Release a shamed user early from containment |
