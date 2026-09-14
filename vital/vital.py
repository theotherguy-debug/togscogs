import asyncio
import json
import logging
import random
from pathlib import Path
import discord
from discord import ui
from redbot.core import commands, Config, bank

log = logging.getLogger("red.WellBeingReminders")


class VitalAcknowledgeView(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=86400) # 24h timeout
        self.bot = bot
        self.acknowledged_users = set()
        
    @ui.button(label="Acknowledge Check-In", style=discord.ButtonStyle.success, emoji="✅")
    async def ack_btn(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id in self.acknowledged_users:
            return await interaction.response.send_message("❌ You have already collected your wellbeing stipend for this check-in.", ephemeral=True)
            
        self.acknowledged_users.add(interaction.user.id)
        stipend = 100
        try:
            await bank.deposit_credits(interaction.user, stipend)
            currency = await bank.get_currency_name(interaction.guild)
            await interaction.response.send_message(f"✅ **HEALTH PROTOCOL ACKNOWLEDGED:** You received a **{stipend} {currency}** stipend. Stay healthy, operative.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("✅ Health protocol acknowledged.", ephemeral=True)

class Vital(commands.Cog):
    """System terminal-style automated reminders with anti-duplication."""
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=84736294857, force_registration=True)
        self.config.register_global(
            channels=[],
            min_wait=3,
            max_wait=6,
            custom_alerts=[]
        )
        self.json_path = Path(__file__).parent / "alerts.json"
        
        # History tracking list to prevent recent message duplication
        self.recent_history = []
        self.json_alerts = []
        
        # Load alerts from json file immediately on startup
        self.load_json_alerts_sync()
        
        self.bg_task = asyncio.create_task(self.managed_reminder_loop())

    def cog_unload(self):
        """Cancel background tasks when the cog is unloaded."""
        if self.bg_task:
            self.bg_task.cancel()

    def load_json_alerts_sync(self):
        """Load alerts from alerts.json into memory cache."""
        if not self.json_path.exists():
            log.warning(f"[WellBeingReminders] alerts.json not found at {self.json_path}")
            self.json_alerts = []
            return
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.json_alerts = data
                log.info(f"[WellBeingReminders] Loaded {len(data)} items from alerts.json")
            elif isinstance(data, dict):
                for key in ["messages", "alerts"]:
                    if key in data and isinstance(data[key], list):
                        self.json_alerts = data[key]
                        log.info(f"[WellBeingReminders] Loaded {len(data[key])} items from alerts.json key '{key}'")
                        return
            else:
                log.warning("[WellBeingReminders] alerts.json exists but is formatted incorrectly.")
        except Exception as e:
            log.error(f"[WellBeingReminders] Error parsing alerts.json: {e}")
            self.json_alerts = []

    async def delete_after(self, message, delay=86400):
        """Delete a message after a specified delay."""
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except discord.HTTPException:
            pass

    def format_alert(self, alert) -> str:
        """Helper to format either a dictionary alert or string alert into the aesthetic ASCII layout."""
        # ANSI escape codes for Discord status/terminal theme colors
        RED = "\u001b[1;31m"
        GREEN = "\u001b[1;32m"
        YELLOW = "\u001b[1;33m"
        CYAN = "\u001b[1;36m"
        WHITE = "\u001b[1;37m"
        GRAY = "\u001b[1;30m"
        RESET = "\u001b[0m"

        if isinstance(alert, dict):
            threat = alert.get("threat", "Unknown.Threat.EXE")
            status = alert.get("status", "ACTIVE")
            alert_msg = alert.get("alert", "N/A")
            access = alert.get("access", "N/A")
            note = alert.get("note", "N/A")
            action = alert.get("action", "N/A")
            
            # Clean up note if it contains a nested alert box to look neat
            if "CRITICAL SYSTEM ALERT" in note:
                note_display = f"\n{note}"
            else:
                note_display = f"\"{note}\""
            
            return (
                f"{RED}╔═════════════════════════════════════════╗{RESET}\n"
                f"{RED}║          CRITICAL SYSTEM ALERT          ║{RESET}\n"
                f"{RED}╚═════════════════════════════════════════╝{RESET}\n\n"
                f" {RED}[!] SYSTEM COMPROMISE DETECTED{RESET}\n"
                f" {RED}[!] STATUS: {status} [⚠️ ALERT]{RESET}\n\n"
                f" {CYAN}[!] DETECTED THREAT:{RESET} {WHITE}{threat}{RESET}\n"
                f" {CYAN}[!] ALERT:{RESET} {WHITE}{alert_msg}{RESET}\n"
                f" {CYAN}[!] ACCESS:{RESET} {WHITE}{access}{RESET}\n"
                f" {CYAN}[!] USER NOTE:{RESET} {YELLOW}{note_display}{RESET}\n\n"
                f" {GREEN}📥 {action}{RESET}\n"
                f" {GRAY}[{RESET}{GREEN}██████████{RESET}{GRAY}          ] 100%{RESET}"
            )
        elif isinstance(alert, str):
            # If it's already a formatted ASCII box, return it directly
            if "CRITICAL SYSTEM ALERT" in alert:
                return alert
            # Format simple string alerts nicely
            return (
                f"{RED}╔═════════════════════════════════════════╗{RESET}\n"
                f"{RED}║          CRITICAL SYSTEM ALERT          ║{RESET}\n"
                f"{RED}╚═════════════════════════════════════════╝{RESET}\n\n"
                f" {RED}[!] SYSTEM COMPROMISE DETECTED{RESET}\n"
                f" {RED}[!] STATUS: ACTIVE [⚠️ ALERT]{RESET}\n\n"
                f" {CYAN}[!] USER NOTE:{RESET} {YELLOW}{alert}{RESET}\n\n"
                f" {GREEN}📥 REMINDER LOGGED{RESET}\n"
                f" {GRAY}[{RESET}{GREEN}██████████{RESET}{GRAY}          ] 100%{RESET}"
            )
        return str(alert)

    def build_alert_embed(self, payload):
        """Build the embed structure for the reminder."""
        formatted_payload = self.format_alert(payload)
        return discord.Embed(
            title="⚠️ Critical System Alert",
            description=f"```ansi\n{formatted_payload}```",
            color=discord.Color.red()
        ).set_footer(text="Automated Well-Being System")

    async def get_random_message(self):
        """Fetch a non-repeating random alert from all combined message sources."""
        base_messages = [
            {
                "threat": "Extreme.Dehydration.APT",
                "status": "ACTIVE",
                "alert": "Your fluids are running lower than your standards.",
                "access": "Internal plumbing operating on pure sand and regret.",
                "note": "Go chug some water. Your pee shouldn't look like ink.",
                "action": "EMERGENCY REHYDRATION REQUIRED."
            },
            {
                "threat": "Biohazard.Stench.EXE",
                "status": "CRITICAL",
                "alert": "Extreme swamp-ass detected emitting from the operator area.",
                "access": "External pheromones have mutated into a chemical weapon.",
                "note": "Step away from the desk and shower. Use soap this time.",
                "action": "CONGENITAL DECONTAMINATION PROTOCOL."
            }
        ]
        
        custom_alerts = await self.config.custom_alerts()
        
        # Combine all messages
        all_messages = base_messages + self.json_alerts + custom_alerts
        
        if not all_messages:
            return "[!] SYSTEM ALERT\n\nUSER NOTE: Reminders pool is empty."

        # Filter out alerts that ran recently
        available_choices = [msg for msg in all_messages if msg not in self.recent_history]
        
        # If pool is exhausted or too small, purge the oldest history entries to free choices
        if not available_choices or len(available_choices) < 1:
            self.recent_history.clear()
            available_choices = all_messages
            
        chosen_message = random.choice(available_choices)
        
        # Keep track of history up to roughly half of the total available pool size
        max_history_len = max(1, len(all_messages) // 2)
        self.recent_history.append(chosen_message)
        if len(self.recent_history) > max_history_len:
            self.recent_history.pop(0)
            
        return chosen_message

    async def managed_reminder_loop(self):
        """A robust dynamic loop replacing ext.tasks for random variable intervals."""
        await self.bot.wait_until_ready()
        try:
            while True:
                min_h = await self.config.min_wait()
                max_h = await self.config.max_wait()
                total_seconds = random.randint(min_h * 3600, max_h * 3600)
                
                while total_seconds > 0:
                    sleep_chunk = min(total_seconds, 900)
                    await asyncio.sleep(sleep_chunk)
                    total_seconds -= sleep_chunk
                    
                channels = await self.config.channels()
                if not channels:
                    continue
                    
                payload = await self.get_random_message()
                embed = self.build_alert_embed(payload)
                
                for channel_id in channels:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        continue
                    try:
                        view = VitalAcknowledgeView(self.bot)
                        msg = await channel.send(embed=embed, view=view)
                        asyncio.create_task(self.delete_after(msg))
                    except discord.Forbidden:
                        continue
        except asyncio.CancelledError:
            pass

    @commands.hybrid_group(aliases=["sys"])
    @commands.admin_or_permissions(manage_guild=True)
    async def system(self, ctx):
        """Configure the Critical System Alerts."""
        pass

    @system.command()
    async def interval(self, ctx, min_hours: int, max_hours: int):
        """Set the random wait time (in hours) between alerts."""
        if min_hours < 1 or max_hours <= min_hours:
            return await ctx.send("⚠️ Invalid interval.")
        await self.config.min_wait.set(min_hours)
        await self.config.max_wait.set(max_hours)
        await ctx.send(f"⏱️ Interval set to {min_hours}–{max_hours} hours. The loop will adapt dynamically.")

    @system.command()
    async def addalert(self, ctx, *, text: str):
        """Add a custom text reminder string."""
        async with self.config.custom_alerts() as alerts:
            alerts.append(text)
        await ctx.send("✅ Added to rotation!")

    @system.command()
    async def removealert(self, ctx, index: int):
        """Remove a custom alert by its 1-based index (from listalerts)."""
        async with self.config.custom_alerts() as alerts:
            if 1 <= index <= len(alerts):
                removed = alerts.pop(index - 1)
                await ctx.send(f"✅ Removed custom alert #{index}: {removed[:50]}...")
            else:
                await ctx.send(f"⚠️ Invalid index. Must be between 1 and {len(alerts)}.")

    @system.command()
    async def addchannel(self, ctx):
        """Add current channel to the dispatch list."""
        async with self.config.channels() as channels:
            if ctx.channel.id not in channels:
                channels.append(ctx.channel.id)
                await ctx.send(f"✅ Added {ctx.channel.mention} to broadcast list.")
            else:
                await ctx.send("⚠️ This channel is already on the broadcast list.")

    @system.command()
    async def removechannel(self, ctx):
        """Remove current channel from the dispatch list."""
        async with self.config.channels() as channels:
            if ctx.channel.id in channels:
                channels.remove(ctx.channel.id)
                await ctx.send(f"✅ Removed {ctx.channel.mention} from broadcast list.")
            else:
                await ctx.send("⚠️ This channel is not on the broadcast list.")

    @system.command()
    async def reloadalerts(self, ctx):
        """Reload the alerts.json file from disk."""
        await self.bot.loop.run_in_executor(None, self.load_json_alerts_sync)
        await ctx.send(f"🔄 Reloaded alerts.json. Currently loaded: {len(self.json_alerts)} file alerts.")

    @system.command()
    async def listalerts(self, ctx):
        """List all currently active alert types across all files/DB systems."""
        custom_alerts = await self.config.custom_alerts()
        
        msg = "**--- Core Hardcoded Alerts ---**\n- Extreme.Dehydration.APT\n- Biohazard.Stench.EXE\n\n"
        
        msg += f"**--- JSON File Alerts ({len(self.json_alerts)} Loaded) ---**\n"
        if self.json_alerts:
            for alert in self.json_alerts:
                threat = alert.get("threat", "Unknown") if isinstance(alert, dict) else str(alert)
                msg += f"- {threat}\n"
        else:
            msg += "*No JSON alerts detected.*\n"
            
        msg += f"\n**--- Config Database Alerts ({len(custom_alerts)} Loaded) ---**\n"
        if custom_alerts:
            for idx, alert in enumerate(custom_alerts, 1):
                snippet = alert[:50] + "..." if len(str(alert)) > 50 else alert
                msg += f"{idx}. {snippet}\n"
        else:
            msg += "*No DB custom alerts setup.*"
            
        if len(msg) > 2000:
            for chunk in [msg[i:i+1900] for i in range(0, len(msg), 1900)]:
                await ctx.send(chunk)
        else:
            await ctx.send(msg)

    @system.command()
    async def test(self, ctx, *, threat_name: str = None):
        """Fire a test embed. If threat_name is provided, tests that specific alert."""
        base_messages = [
            {
                "threat": "Extreme.Dehydration.APT",
                "status": "ACTIVE",
                "alert": "Your fluids are running lower than your standards.",
                "access": "Internal plumbing operating on pure sand and regret.",
                "note": "Go chug some water. Your pee shouldn't look like ink.",
                "action": "EMERGENCY REHYDRATION REQUIRED."
            },
            {
                "threat": "Biohazard.Stench.EXE",
                "status": "CRITICAL",
                "alert": "Extreme swamp-ass detected emitting from the operator area.",
                "access": "External pheromones have mutated into a chemical weapon.",
                "note": "Step away from the desk and shower. Use soap this time.",
                "action": "CONGENITAL DECONTAMINATION PROTOCOL."
            }
        ]
        
        all_messages = base_messages + self.json_alerts
        
        if threat_name:
            matched = None
            for alert in all_messages:
                if isinstance(alert, dict) and alert.get("threat", "").lower() == threat_name.lower():
                    matched = alert
                    break
            
            if matched:
                embed = self.build_alert_embed(matched)
                msg = await ctx.send(embed=embed, view=VitalAcknowledgeView(self.bot))
                asyncio.create_task(self.delete_after(msg, 300))
                if ctx.interaction is None: 
                    asyncio.create_task(self.delete_after(ctx.message, 300))
            else:
                await ctx.send(f"⚠️ Threat '{threat_name}' not found in loaded alerts. Use `[p]sys listalerts` to see loaded threat names.")
        else:
            payload = await self.get_random_message()
            embed = self.build_alert_embed(payload)
            msg = await ctx.send(embed=embed, view=VitalAcknowledgeView(self.bot))
            asyncio.create_task(self.delete_after(msg, 300))
            if ctx.interaction is None: 
                asyncio.create_task(self.delete_after(ctx.message, 300))
