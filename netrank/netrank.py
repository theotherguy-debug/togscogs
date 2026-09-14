import discord
import asyncio
import time
import math
from discord.ext import tasks
from typing import Optional, Dict, List
from redbot.core import commands, Config, bank
from discord import ui

# --- ANSI Terminal Colors ---
RED = "\u001b[1;31m"
GREEN = "\u001b[1;32m"
YELLOW = "\u001b[1;33m"
CYAN = "\u001b[1;36m"
WHITE = "\u001b[1;37m"
DARK_GRAY = "\u001b[1;30m"
RESET = "\u001b[0m"


class NetRank(commands.Cog):
    """Server-wide cybersecurity/cyberpunk XP and leveling system."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8923487319, force_registration=True)

        default_guild = {
            "xp_sources": {
                "counts": True,
                "duels": True,
                "survivor": True,
                "messages": False,
                "voice": True
            },
            "xp_per_count": 10,
            "xp_per_duel_win": 250,
            "xp_per_survivor_milestone": 500,
            "xp_per_message": 5,
            "message_xp_cooldown": 60,
            "xp_per_voice_minute": 2,
            "voice_xp_interval": 60,  # Award XP every 60 seconds in VC
            "voice_min_members": 2,  # Minimum members needed to earn XP
            "level_up_channel_id": None,
            "level_roles": {},  # str(level) -> role_id
            "rank_enabled": True,
            "credits_per_level": 500
        }

        default_member = {
            "xp": 0,
            "level": 0,
            "last_message_xp_time": 0.0,
            "last_voice_xp_time": 0.0,
            "voice_session_start": 0.0
        }

        self.config.register_guild(**default_guild)
        self.config.register_member(**default_member)

        # Start background tasks
        self.voice_xp_checker.start()

    def cog_unload(self):
        """Clean up background tasks when cog is unloaded."""
        self.voice_xp_checker.cancel()

    # --- XP and Level Helpers ---

    def xp_for_level(self, level: int) -> int:
        """Calculate the absolute XP needed to unlock a level."""
        if level <= 0:
            return 0
        return int(150 * (level ** 1.7))

    def get_level_from_xp(self, xp: int) -> int:
        """Find current level from total accumulated XP using binary search."""
        if xp < 100:
            return 0
        
        low = 1
        high = 500  # Reasonable cap for fast checks, can go higher if needed
        current_lvl = 0
        
        while low <= high:
            mid = (low + high) // 2
            if self.xp_for_level(mid) <= xp:
                current_lvl = mid
                low = mid + 1
            else:
                high = mid - 1
        return current_lvl

    def get_rank_tier(self, level: int) -> str:
        """Get the cybersecurity tier name based on level."""
        if level < 5:
            return "Script Kiddie"
        elif level < 10:
            return "Novice Operator"
        elif level < 15:
            return "Field Technician"
        elif level < 20:
            return "Security Analyst"
        elif level < 30:
            return "Network Infiltrator"
        elif level < 40:
            return "Cyber Architect"
        elif level < 50:
            return "Shadow Protocol"
        elif level < 75:
            return "Ghost in the Shell"
        elif level < 100:
            return "System Administrator"
        else:
            return "ROOT ACCESS"

    async def add_xp(self, member: discord.Member, amount: int, channel: Optional[discord.TextChannel] = None):
        """Add XP to a member, calculate level ups, assign roles, and trigger announcements."""
        guild = member.guild
        if not await self.config.guild(guild).rank_enabled():
            return

        async with self.config.member(member).all() as data:
            old_xp = data["xp"]
            new_xp = old_xp + amount
            data["xp"] = new_xp

            old_level = data["level"]
            new_level = self.get_level_from_xp(new_xp)
            
            if new_level > old_level:
                data["level"] = new_level
                # Trigger level up process in background to prevent blocking
                asyncio.create_task(self.handle_level_up(member, new_level, channel))

    async def handle_level_up(self, member: discord.Member, level: int, channel: Optional[discord.TextChannel]):
        """Assign role rewards and announce level-ups."""
        guild = member.guild
        
        # 1. Level role assignments
        level_roles = await self.config.guild(guild).level_roles()
        assigned_role_msg = ""
        
        if str(level) in level_roles:
            role_id = level_roles[str(level)]
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason=f"Unlocked level {level} reward!")
                    assigned_role_msg = f"\n🏆 **Access Granted:** Auto-assigned role {role.mention}."
                except discord.Forbidden:
                    pass

        # 2. Prepare announcement text
        tier = self.get_rank_tier(level)
        
        # Give Economy Reward
        credit_reward = 0
        try:
            credits_per_level = await self.config.guild(guild).credits_per_level()
            if credits_per_level > 0:
                credit_reward = level * credits_per_level
                await bank.deposit_credits(member, credit_reward)
                currency = await bank.get_currency_name(guild)
                assigned_role_msg += f"\n💰 **Bonus:** {credit_reward:,} {currency} deposited to bank."
        except Exception:
            pass

        announcement_desc = (
            f"```ansi\n"
            f"{CYAN}╔══════════════════════════════════════════════════════╗{RESET}\n"
            f"{CYAN}║             🟢 SYSTEM ELEVATION DETECTED             ║{RESET}\n"
            f"{CYAN}╚══════════════════════════════════════════════════════╝{RESET}\n\n"
            f" Operative {WHITE}{member.display_name}{RESET} has bypassed mainframe limits!\n"
            f" New Cleared Level: {GREEN}{level}{RESET}\n"
            f" Security Cleared Class: {YELLOW}{tier}{RESET}\n"
            f"```"
        )
        
        embed = discord.Embed(
            title="⚡ Operative Level Up!",
            description=announcement_desc + (assigned_role_msg if assigned_role_msg else ""),
            color=discord.Color.teal()
        )

        # 3. Deliver announcements
        # Broadcast channel announcement
        level_up_channel_id = await self.config.guild(guild).level_up_channel_id()
        if level_up_channel_id:
            broadcast_ch = guild.get_channel(level_up_channel_id)
            if broadcast_ch:
                try:
                    await broadcast_ch.send(embed=embed)
                except discord.Forbidden:
                    pass

        # Self-deleting announcement in local channel
        if channel:
            try:
                local_msg = await channel.send(embed=embed)
                # Self delete after 10 minutes (600s)
                await asyncio.sleep(600)
                await local_msg.delete()
            except Exception:
                pass

    # --- Event Hook Listeners ---

    @commands.Cog.listener()
    async def on_netcount_valid_count(self, message: discord.Message, expected_number: int):
        """Hook into counting successes."""
        guild = message.guild
        if not guild:
            return
        
        sources = await self.config.guild(guild).xp_sources()
        if not sources.get("counts", True):
            return

        base_xp = await self.config.guild(guild).xp_per_count()
        # Scale XP with streak depth (e.g. 1-99 is 1x, 100-199 is 2x, 200-299 is 3x, etc.)
        multiplier = max(1, expected_number // 100 + 1)
        xp_to_award = base_xp * multiplier

        await self.add_xp(message.author, xp_to_award, message.channel)

    @commands.Cog.listener()
    async def on_netcount_duel_complete(self, guild: discord.Guild, winner: discord.Member, loser: discord.Member, wager: int, final_count: int):
        """Hook into duel outcomes. Only rewards XP when wager = 0."""
        if wager > 0:
            return  # No XP for gambling duels
        
        sources = await self.config.guild(guild).xp_sources()
        if not sources.get("duels", True):
            return

        xp_to_award = await self.config.guild(guild).xp_per_duel_win()
        
        # Send announcement in the general channel or notify locally
        await self.add_xp(winner, xp_to_award, None)

    @commands.Cog.listener()
    async def on_netcount_survivor_milestone(self, guild: discord.Guild, milestone: int, contributors: dict):
        """Hook into survivor milestone completions. Distribute XP to contributors."""
        sources = await self.config.guild(guild).xp_sources()
        if not sources.get("survivor", True):
            return

        base_xp = await self.config.guild(guild).xp_per_survivor_milestone()
        total_contrib = sum(contributors.values())
        if total_contrib <= 0:
            return

        for user_id, count in contributors.items():
            member = guild.get_member(user_id)
            if member:
                # XP proportional to contribution
                share = count / total_contrib
                xp_to_award = int(base_xp * share)
                if xp_to_award > 0:
                    await self.add_xp(member, xp_to_award, None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen to general messages for activity XP (with anti-spam cooldown)."""
        if message.author.bot or not message.guild:
            return

        guild = message.guild
        sources = await self.config.guild(guild).xp_sources()
        if not sources.get("messages", False):
            return

        # Check if the channel is a NetCount counting channel. 
        # We don't want to double reward counting messages from here.
        netcount_cog = self.bot.get_cog("NetCount")
        if netcount_cog:
            netcount_channels = await netcount_cog.config.guild(guild).channels()
            if str(message.channel.id) in netcount_channels:
                return

        cooldown = await self.config.guild(guild).message_xp_cooldown()
        last_xp_time = await self.config.member(message.author).last_message_xp_time()
        now = time.time()

        if now - last_xp_time >= cooldown:
            xp_to_award = await self.config.guild(guild).xp_per_message()
            await self.config.member(message.author).last_message_xp_time.set(now)
            await self.add_xp(message.author, xp_to_award, message.channel)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Track voice channel join/leave for XP session management."""
        if member.bot:
            return

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            if after.afk:
                return
            await self.config.member(member).voice_session_start.set(time.time())
            await self.config.member(member).last_voice_xp_time.set(0.0)

        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            await self.config.member(member).voice_session_start.set(0.0)
            await self.config.member(member).last_voice_xp_time.set(0.0)

        # User switched channels
        elif before.channel is not None and after.channel is not None:
            await self.config.member(member).voice_session_start.set(time.time())
            await self.config.member(member).last_voice_xp_time.set(0.0)

    @tasks.loop(seconds=60)
    async def voice_xp_checker(self):
        """Background task to award voice channel XP every minute."""
        for guild in self.bot.guilds:
            sources = await self.config.guild(guild).xp_sources()
            if not sources.get("voice", True):
                continue

            xp_per_minute = await self.config.guild(guild).xp_per_voice_minute()
            min_members = await self.config.guild(guild).voice_min_members()
            now = time.time()

            for member in guild.members:
                if member.bot:
                    continue

                # Check if member is in a voice channel
                if not member.voice or not member.voice.channel:
                    continue

                # Check if AFK
                if member.voice.afk:
                    continue

                # Check minimum members requirement (non-bot only)
                channel = member.voice.channel
                non_bot_members = [m for m in channel.members if not m.bot]
                if len(non_bot_members) < min_members:
                    continue

                # Check cooldown
                last_voice_xp = await self.config.member(member).last_voice_xp_time()
                if now - last_voice_xp < 60:
                    continue

                # Award XP
                await self.config.member(member).last_voice_xp_time.set(now)
                await self.add_xp(member, xp_per_minute, channel)

    @voice_xp_checker.before_loop
    async def before_voice_xp_checker(self):
        await self.bot.wait_until_red_ready()

    # --- User-Facing Commands ---

    @commands.hybrid_command(name="rank", aliases=["level", "xp"])
    @commands.guild_only()
    async def rank(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """View your operative level, experience points, and server rank."""
        member = member or ctx.author
        guild = ctx.guild

        if not await self.config.guild(guild).rank_enabled():
            return await ctx.send("❌ The ranking mainframe is currently offline on this node.")

        await ctx.defer()

        # Get all members in guild to determine global rank sorted by XP
        all_members = await self.config.all_members(guild)
        sorted_members = sorted(all_members.items(), key=lambda x: x[1]["xp"], reverse=True)
        
        user_rank = 0
        total_players = 0
        for i, (uid, data) in enumerate(sorted_members, 1):
            guild_member = guild.get_member(uid)
            if guild_member and not guild_member.bot:
                total_players += 1
                if uid == member.id:
                    user_rank = total_players

        # Get member config info
        member_data = await self.config.member(member).all()
        current_xp = member_data["xp"]
        current_level = member_data["level"]
        
        current_lvl_xp_start = self.xp_for_level(current_level)
        next_lvl_xp_start = self.xp_for_level(current_level + 1)
        
        progress = current_xp - current_lvl_xp_start
        required = next_lvl_xp_start - current_lvl_xp_start
        
        if required <= 0:
            percentage = 100.0
        else:
            percentage = min(100.0, (progress / required) * 100)

        # Build progress bar (20 chars long)
        bar_length = 20
        filled = int((percentage / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        tier = self.get_rank_tier(current_level)

        card_desc = (
            f"```ansi\n"
            f"{CYAN}╔══════════════════════════════════════════════════════╗{RESET}\n"
            f"{CYAN}║               SYSTEM OPERATIVE DOS: 4.1              ║{RESET}\n"
            f"{CYAN}╚══════════════════════════════════════════════════════╝{RESET}\n\n"
            f"  OPERATIVE:   {WHITE}{member.name}#{member.discriminator}{RESET}\n"
            f"  ACCESS LVL:  {GREEN}{current_level}{RESET} [{YELLOW}{tier}{RESET}]\n"
            f"  GLOBAL RANK: {CYAN}#{user_rank if user_rank > 0 else 'N/A'}{RESET} / {total_players}\n\n"
            f"  SYSTEM INDEX PROGRESSION:\n"
            f"  XP: {GREEN}{current_xp:,}{RESET} / {WHITE}{next_lvl_xp_start:,}{RESET} [{percentage:.1f}%]\n"
            f"  {CYAN}[{GREEN}{bar}{CYAN}]{RESET}\n"
            f"```"
        )

        embed = discord.Embed(
            title=f"👤 Operative Profile: {member.display_name}",
            description=card_desc,
            color=discord.Color.dark_blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="Decryption Division • Command Mainframe")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="ranktop", aliases=["leveltop", "ltop"])
    @commands.guild_only()
    async def ranktop(self, ctx: commands.Context):
        """Display the server's top 10 operatives by decrypted XP."""
        guild = ctx.guild

        if not await self.config.guild(guild).rank_enabled():
            return await ctx.send("❌ The ranking mainframe is currently offline on this node.")

        await ctx.defer()

        all_members = await self.config.all_members(guild)
        sorted_members = sorted(all_members.items(), key=lambda x: x[1]["xp"], reverse=True)

        leaderboard_lines = []
        count = 0
        
        for uid, data in sorted_members:
            member = guild.get_member(uid)
            if not member or member.bot:
                continue
            
            count += 1
            rank_str = f"{count:02d}."
            if count == 1:
                rank_color = YELLOW
            elif count == 2:
                rank_color = WHITE
            elif count == 3:
                rank_color = GREEN
            else:
                rank_color = DARK_GRAY

            lvl = data["level"]
            xp = data["xp"]
            
            # Pad name to keep columns aligned
            name_padded = (member.display_name[:22] + "..") if len(member.display_name) > 22 else member.display_name
            name_col = f"{name_padded:<24}"
            
            leaderboard_lines.append(
                f"  {rank_color}{rank_str}{RESET}  {WHITE}{name_col}{RESET}  Lvl {lvl:<4}  {GREEN}{xp:,} XP{RESET}"
            )
            
            if count >= 10:
                break

        if not leaderboard_lines:
            leaderboard_lines.append("  No operatives registered in database.")

        desc = (
            f"```ansi\n"
            f"{CYAN}╔══════════════════════════════════════════════════════╗{RESET}\n"
            f"{CYAN}║            SERVER XP OPERATIVE LEADERBOARD           ║{RESET}\n"
            f"{CYAN}╚══════════════════════════════════════════════════════╝{RESET}\n\n"
            f"  Rank  Operative                 Level     Decrypted XP\n"
            + "\n".join(leaderboard_lines) +
            f"\n```"
        )

        embed = discord.Embed(
            title="🏆 Decryption Leaderboard",
            description=desc,
            color=discord.Color.blue()
        )
        embed.set_footer(text="Data compiled from mainframe records")
        await ctx.send(embed=embed)

    # --- Admin Command Group ---

    @commands.hybrid_group(name="ranking")
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def ranking(self, ctx: commands.Context):
        """Administrative tools to configure the Ranking / Leveling system."""
        pass

    @ranking.command(name="toggle")
    async def ranking_toggle(self, ctx: commands.Context):
        """Toggle the entire ranking/XP system on or off."""
        current = await self.config.guild(ctx.guild).rank_enabled()
        await self.config.guild(ctx.guild).rank_enabled.set(not current)
        status = "ONLINE" if not current else "OFFLINE"
        await ctx.send(f"✅ Mainframe ranking matrix is now **{status}**.")

    @ranking.command(name="setxp")
    async def ranking_setxp(self, ctx: commands.Context, source: str, amount: int):
        """Configure XP rewards per source (counts, duels, survivor, messages, voice)."""
        valid_sources = ["counts", "duels", "survivor", "messages", "voice"]
        source = source.lower()
        if source not in valid_sources:
            return await ctx.send(f"❌ Invalid source. Choose from: {', '.join(valid_sources)}")
        
        if amount < 0:
            return await ctx.send("❌ XP reward amount cannot be negative.")

        if source == "counts":
            await self.config.guild(ctx.guild).xp_per_count.set(amount)
        elif source == "duels":
            await self.config.guild(ctx.guild).xp_per_duel_win.set(amount)
        elif source == "survivor":
            await self.config.guild(ctx.guild).xp_per_survivor_milestone.set(amount)
        elif source == "messages":
            await self.config.guild(ctx.guild).xp_per_message.set(amount)
        elif source == "voice":
            await self.config.guild(ctx.guild).xp_per_voice_minute.set(amount)

        await ctx.send(f"✅ Successfully updated reward parameter. **{source}** now grants **{amount} XP**.")

    @ranking.command(name="levelchannel")
    async def ranking_levelchannel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set a dedicated channel for level-up broadcasts. Pass no channel to clear."""
        if channel:
            await self.config.guild(ctx.guild).level_up_channel_id.set(channel.id)
            await ctx.send(f"✅ Level-up alerts will now be routed to {channel.mention}.")
        else:
            await self.config.guild(ctx.guild).level_up_channel_id.set(None)
            await ctx.send("✅ Level-up broadcast channel cleared. Notifications will only appear locally.")

    @ranking.command(name="setlevelcredits")
    async def ranking_setlevelcredits(self, ctx: commands.Context, amount: int):
        """Set the amount of credits rewarded per level (e.g. 500 means Level 5 gives 2500 credits)."""
        if amount < 0:
            return await ctx.send("❌ Amount cannot be negative.")
        await self.config.guild(ctx.guild).credits_per_level.set(amount)
        await ctx.send(f"✅ Level-up rewards configured: **{amount} credits** per level.")

    @ranking.command(name="roleadd")
    async def ranking_roleadd(self, ctx: commands.Context, level: int, role: discord.Role):
        """Add a role to be rewarded upon reaching a specific level."""
        if level <= 0:
            return await ctx.send("❌ Level must be a positive integer.")
            
        async with self.config.guild(ctx.guild).level_roles() as roles:
            roles[str(level)] = role.id
        await ctx.send(f"🏆 Role reward configured: Reaching level **{level}** will award {role.mention}.")

    @ranking.command(name="roleremove")
    async def ranking_roleremove(self, ctx: commands.Context, level: int):
        """Remove a role reward for a specific level."""
        async with self.config.guild(ctx.guild).level_roles() as roles:
            if str(level) in roles:
                roles.pop(str(level))
                await ctx.send(f"✅ Removed level **{level}** role reward.")
            else:
                await ctx.send(f"❌ No role reward configured for level **{level}**.")

    @ranking.command(name="givexp")
    async def ranking_givexp(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Manually award XP to a specific operative."""
        if amount <= 0:
            return await ctx.send("❌ XP amount must be positive.")
        await self.add_xp(member, amount, ctx.channel)
        await ctx.send(f"⚡ Injected **{amount} XP** into operative {member.mention}'s registry buffer.")

    @ranking.command(name="resetxp")
    async def ranking_resetxp(self, ctx: commands.Context, member: discord.Member):
        """Reset a user's XP and level back to zero."""
        await self.config.member(member).xp.set(0)
        await self.config.member(member).level.set(0)
        await ctx.send(f"🧹 Realigned registry buffer. Operative {member.mention}'s XP and level have been reset to **0**.")

    @ranking.command(name="resetall")
    async def ranking_resetall(self, ctx: commands.Context):
        """Wipe all XP and level progress database records for this guild."""
        await self.config.clear_all_members(ctx.guild)
        await ctx.send("🚨 **DATABASE PURGED:** Cleared all operative levels and XP registry records from this guild.")
