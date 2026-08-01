# Adding Custom XP Sources to NetRank

## Overview

NetRank uses an **event-driven architecture** where XP is awarded through custom Discord.py events. This makes it easy to add new XP sources from any cog without modifying NetRank's core code.

## Current XP Sources

NetRank currently has **4 built-in XP sources**:

| Source | Trigger | Default XP | Conditions |
|:---|:---|:---|:---|
| **Valid Counts** | `on_netcount_valid_count` | 10 × streak multiplier | Every correct count |
| **Duel Wins** | `on_netcount_duel_complete` | 250 (flat) | Only when wager = 0 |
| **Survivor Milestones** | `on_netcount_survivor_milestone` | 500 (split) | Proportional to contributions |
| **Messages** | `on_message` | 5 per message | Disabled by default, 60s cooldown |

---

## How XP is Awarded

### The Core Flow

```
1. Event is dispatched from a cog
   ↓
2. NetRank listener catches the event
   ↓
3. XP amount is calculated
   ↓
4. add_xp(member, amount, channel) is called
   ↓
5. Member's XP is updated in database
   ↓
6. Level is recalculated
   ↓
7. If level increased → handle_level_up() triggers
```

### The `add_xp` Method

All XP flows through this central method:

```python
async def add_xp(self, member: discord.Member, amount: int, channel: Optional[discord.TextChannel] = None):
    """Add XP to a member, calculate level ups, assign roles, and trigger announcements."""
    guild = member.guild
    if not await self.config.guild(guild).rank_enabled():
        return  # Ranking system is disabled

    async with self.config.member(member).all() as data:
        old_xp = data["xp"]
        new_xp = old_xp + amount
        data["xp"] = new_xp

        old_level = data["level"]
        new_level = self.get_level_from_xp(new_xp)
        
        if new_level > old_level:
            data["level"] = new_level
            # Trigger level up process in background
            asyncio.create_task(self.handle_level_up(member, new_level, channel))
```

**Key points**:
- Automatically checks if ranking is enabled
- Updates XP atomically (thread-safe)
- Calculates new level
- Only triggers level-up if level actually increased
- Level-up announcements run in background to avoid blocking

---

## How to Add a New XP Source

### Step 1: Dispatch an Event from Your Cog

In your cog, dispatch a custom event whenever you want to award XP:

```python
# In your cog's code
self.bot.dispatch("your_event_name", member, xp_amount, channel)
```

### Step 2: Add a Listener in NetRank

Add an event listener in NetRank to catch your event:

```python
@commands.Cog.listener()
async def on_your_event_name(self, member: discord.Member, xp_amount: int, channel: discord.TextChannel):
    """Award XP from your custom source."""
    # Optional: Check if source is enabled in config
    sources = await self.config.guild(member.guild).xp_sources()
    if not sources.get("your_source_name", True):
        return
    
    # Award the XP
    await self.add_xp(member, xp_amount, channel)
```

### Step 3: Add Config Options (Optional)

If you want admins to control your XP source:

```python
# In NetRank's default_guild config:
default_guild = {
    "xp_sources": {
        "counts": True,
        "duels": True,
        "survivor": True,
        "messages": False,
        "your_source": True  # Add your source here
    },
    "xp_per_your_source": 100,  # Add your XP amount
    # ... other settings
}
```

Then add a command to configure it:

```python
@ranking.command(name="setxp")
async def ranking_setxp(self, ctx: commands.Context, source: str, amount: int):
    valid_sources = ["counts", "duels", "survivor", "messages", "your_source"]
    # ... validation logic
    if source == "your_source":
        await self.config.guild(ctx.guild).xp_per_your_source.set(amount)
```

---

## Example: Adding XP for Chat Activity

Let's add a new XP source that awards XP for using slash commands.

### In Your Cog (e.g., `mycog.py`):

```python
class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction, command):
        """Award XP when a slash command is used."""
        # Don't award XP to bots
        if interaction.user.bot:
            return
        
        # Award 15 XP per command use
        xp_amount = 15
        
        # Dispatch event for NetRank to catch
        self.bot.dispatch("mycog_command_used", interaction.user, xp_amount, interaction.channel)
```

### In NetRank (add to `netrank.py`):

```python
@commands.Cog.listener()
async def on_mycog_command_used(self, member: discord.Member, xp_amount: int, channel: discord.TextChannel):
    """Award XP for using commands from MyCog."""
    sources = await self.config.guild(member.guild).xp_sources()
    if not sources.get("commands", True):  # Add "commands" to xp_sources dict
        return
    
    await self.add_xp(member, xp_amount, channel)
```

### Configuration (optional):

Add to NetRank's config and commands to allow server admins to enable/disable and adjust XP:

```python
# In __init__ default_guild:
default_guild = {
    "xp_sources": {
        # ... existing sources
        "commands": False  # Disabled by default
    },
    "xp_per_command": 15
}

# Add command:
@ranking.command(name="setxp")
async def ranking_setxp(self, ctx: commands.Context, source: str, amount: int):
    valid_sources = ["counts", "duels", "survivor", "messages", "commands"]
    # ... existing logic
    elif source == "commands":
        await self.config.guild(ctx.guild).xp_per_command.set(amount)
```

---

## Example: Adding XP for Event Participation

Let's add XP for participating in server events (e.g., game nights, contests).

### In Your Event Manager Cog:

```python
class EventManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def award_event_participation(self, member: discord.Member, event_type: str):
        """Award XP based on event type."""
        xp_rewards = {
            "game_night": 100,
            "contest_winner": 500,
            "contest_participant": 50,
            "trivia": 75
        }
        
        xp = xp_rewards.get(event_type, 25)
        self.bot.dispatch("event_participation", member, xp, None)
```

### In NetRank:

```python
@commands.Cog.listener()
async def on_event_participation(self, member: discord.Member, xp_amount: int, channel):
    """Award XP for event participation."""
    await self.add_xp(member, xp_amount, channel)
```

---

## Advanced: Conditional XP Awards

You can add logic to control when XP is awarded:

```python
@commands.Cog.listener()
async def on_custom_event(self, member: discord.Member, xp_amount: int, channel):
    # Only award on weekdays
    import datetime
    if datetime.datetime.now().weekday() >= 5:  # 5=Saturday, 6=Sunday
        return
    
    # Only award if member has been in server for 7+ days
    if (datetime.datetime.now() - member.joined_at).days < 7:
        return
    
    # Award 2x XP for Nitro boosters
    if member.premium_since:
        xp_amount *= 2
    
    await self.add_xp(member, xp_amount, channel)
```

---

## Advanced: XP Bonuses and Multipliers

### Time-Based Bonuses

```python
@commands.Cog.listener()
async def on_message(self, message):
    if message.author.bot:
        return
    
    # 2x XP during happy hour (6PM-8PM UTC)
    hour = datetime.datetime.now(datetime.timezone.utc).hour
    multiplier = 2 if 18 <= hour < 20 else 1
    
    base_xp = 10
    xp = int(base_xp * multiplier)
    
    self.bot.dispatch("custom_message_xp", message.author, xp, message.channel)
```

### Role-Based Bonuses

```python
@commands.Cog.listener()
async def on_netcount_valid_count(self, message, expected_number):
    base_xp = 10
    multiplier = max(1, expected_number // 100 + 1)
    
    # VIP role gets 1.5x XP
    vip_role = discord.utils.get(message.author.roles, name="VIP")
    if vip_role:
        multiplier *= 1.5
    
    xp = int(base_xp * multiplier)
    self.bot.dispatch("custom_count_xp", message.author, xp, message.channel)
```

---

## Best Practices

### 1. Always Check for Bots

```python
if member.bot:
    return
```

### 2. Use Configurable Values

Don't hardcode XP amounts. Use the config system:

```python
# Good
xp_amount = await self.config.guild(guild).xp_per_my_source()

# Bad
xp_amount = 999  # Hardcoded
```

### 3. Respect the Master Toggle

```python
if not await self.config.guild(guild).rank_enabled():
    return
```

### 4. Use Background Tasks for Heavy Operations

If your XP award triggers expensive operations, use asyncio:

```python
asyncio.create_task(self.process_heavy_xp_logic(member, xp))
```

### 5. Handle Missing Permissions

```python
try:
    await self.add_xp(member, xp, channel)
except discord.Forbidden:
    # Bot lacks permissions, skip silently
    pass
except Exception as e:
    # Log error
    print(f"Failed to award XP: {e}")
```

---

## Testing Your XP Source

### 1. Enable Debug Mode

```bash
[p]ranking toggle  # Make sure it's ON
```

### 2. Check XP Awarded

```bash
[p]rank @YourUsername
```

### 3. Verify in Database

```bash
[p]debug
# Look for netrank config data
```

### 4. Monitor Level-Ups

Check if level-up announcements appear when XP threshold is crossed.

---

## Complete Example: XP for Voice Channel Activity

Here's a full example of adding XP for time spent in voice channels.

### In Your Voice Tracker Cog:

```python
class VoiceTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_timers = {}  # user_id -> start_time

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            self.voice_timers[member.id] = time.time()
        
        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            if member.id in self.voice_timers:
                start_time = self.voice_timers.pop(member.id)
                duration_minutes = (time.time() - start_time) / 60
                
                # Award 1 XP per minute, minimum 5 XP
                xp = max(5, int(duration_minutes))
                
                # Dispatch event
                self.bot.dispatch("voice_time_earned", member, xp, before.channel)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Handle AFK channel (no XP)
        if after.channel and after.afk:
            if member.id in self.voice_timers:
                del self.voice_timers[member.id]
            return
```

### In NetRank:

```python
@commands.Cog.listener()
async def on_voice_time_earned(self, member: discord.Member, xp_amount: int, channel):
    """Award XP for voice channel participation."""
    sources = await self.config.guild(member.guild).xp_sources()
    if not sources.get("voice", False):  # Add "voice" to config
        return
    
    await self.add_xp(member, xp_amount, channel)
```

### Add to Config:

```python
# In __init__:
default_guild = {
    "xp_sources": {
        # ... existing
        "voice": False  # New source
    },
    "xp_per_voice_minute": 1
}

# In setxp command:
elif source == "voice":
    await self.config.guild(ctx.guild).xp_per_voice_minute.set(amount)
```

---

## Removing or Disabling XP Sources

### Disable via Config

```bash
# Disable a source
[p]ranking setxp counts 0
```

Or edit the sources dict:

```python
sources = await self.config.guild(guild).xp_sources()
sources["counts"] = False
await self.config.guild(guild).xp_sources.set(sources)
```

### Remove Event Listener

If you want to completely remove an XP source from NetRank:

1. Comment out or delete the event listener in `netrank.py`
2. Remove from `xp_sources` config default
3. Remove from `setxp` command validation

**Note**: You cannot unload an event listener at runtime in Red-DiscordBot. You would need to reload the cog.

---

## Performance Considerations

### Batch XP Awards

If awarding XP to multiple members at once:

```python
# Good: Batch update
async with self.config.guild(guild).all_members() as members_data:
    for member_id, data in members_data.items():
        data["xp"] += xp_amount

# Bad: Individual updates (slow)
for member_id in member_ids:
    await self.add_xp(member, xp_amount, channel)
```

### Debounce Rapid Events

For events that fire rapidly (like messages):

```python
@commands.Cog.listener()
async def on_my_rapid_event(self, member, data):
    # Only award XP every 60 seconds
    last_award = await self.config.member(member).last_rapid_event_time()
    now = time.time()
    
    if now - last_award < 60:
        return
    
    await self.config.member(member).last_rapid_event_time.set(now)
    await self.add_xp(member, 10, None)
```

---

## Summary

**To add a new XP source:**

1. **Dispatch event** from your cog when you want to award XP
2. **Add listener** in NetRank to catch the event
3. **Call `add_xp()`** with the member and amount
4. **Optional**: Add config options for admins to control it

**Key benefits:**
- No need to modify NetRank core logic
- Event-driven = decoupled and maintainable
- All XP flows through one method (consistent level calculation)
- Easy to enable/disable via config
- Can be added from any cog

---

## Quick Reference

### Event Signature Template

```python
# Your cog dispatches:
self.bot.dispatch("event_name", member, xp_amount, channel)

# NetRank listens:
@commands.Cog.listener()
async def on_event_name(self, member: discord.Member, xp_amount: int, channel):
    sources = await self.config.guild(member.guild).xp_sources()
    if not sources.get("source_key", True):
        return
    await self.add_xp(member, xp_amount, channel)
```

### Common Patterns

| Pattern | Use Case | Example |
|:---|:---|:---|
| Flat XP | Simple rewards | `xp = 50` |
| Time-based | Voice, activity | `xp = int(minutes)` |
| Multiplier-based | Streaks, tiers | `xp = base * multiplier` |
| Proportional | Split rewards | `xp = total * (user_share)` |
| Conditional | Bonuses | `xp = base * 2 if VIP else base` |