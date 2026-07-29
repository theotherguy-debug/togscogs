import discord
import ast
import operator
import datetime
import random
import time
import asyncio
from typing import Optional
from redbot.core import commands, Config, bank
from discord.ext import tasks

# --- HARDENED MATH PARSER ---
ops = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.BitXor: operator.pow
}

def safe_eval(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise TypeError("Only numbers are allowed.")
    elif getattr(ast, 'Num', None) and isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.BinOp):
        if isinstance(node.op, (ast.Pow, ast.BitXor)):
            right_val = safe_eval(node.right)
            if right_val > 100:  # Cap exponents to prevent CPU DoS
                raise ValueError("Exponent too large!")
            return ops[type(node.op)](safe_eval(node.left), right_val)
        return ops[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        return ops[type(node.op)](safe_eval(node.operand))
    else:
        raise TypeError(f"Unsupported mathematical operation: {type(node)}")

def evaluate_math(expression: str):
    if len(expression) > 50:
        return None 
    try:
        expression = expression.replace('^', '**')
        result = safe_eval(ast.parse(expression, mode='eval').body)
        return float(result) # Float supports true division (e.g., 4/2 = 2.0)
    except (Exception, ValueError, TypeError, ZeroDivisionError):
        return None

def to_monospace(text: str) -> str:
    """Converts alphanumeric characters in text to monospace Unicode counterparts."""
    result = []
    for char in text:
        o = ord(char)
        if 65 <= o <= 90:  # A-Z
            result.append(chr(o + 120367))
        elif 97 <= o <= 122:  # a-z
            result.append(chr(o + 120361))
        elif 48 <= o <= 57:  # 0-9
            result.append(chr(o + 120774))
        else:
            result.append(char)
    return "".join(result)

# --- MAIN COG CLASS ---
class NetCount(commands.Cog):
    """Ultimate High-Stakes Multi-Channel Sequence Game"""

    # --- RANDOM CYBERPUNK MESSAGE REPOSITORIES ---
    DOUBLE_COUNT_REASONS = [
        "[SYS] ALERT: DUAL_PROCESS_ABORT. User attempted to count twice in a row.",
        "[SYS] ERR_509: REPETITIVE_ENTRY. You cannot verify your own packet. Let someone else type!",
        "[SYS] PROCESS_BLOCKED. Running 'single_file_line.exe'... Self-counting loop detected and terminated."
    ]

    WRONG_NUMBER_TEMPLATES = [
        "Wrong number! Expected **{expected}** but got **{got}**.",
        "[SYS] DATA_CORRUPTION. Sequence mismatch: expected **{expected}**, received **{got}**.",
        "[SYS] INDEX_ERROR. Decryption key mismatch. Received **{got}** instead of **{expected}**. Brain reboot recommended."
    ]

    GAME_OVER_TEMPLATES = [
        (
            "{member} ruined the streak at **{streak}** in {channel}!\n"
            "**Reason**: {reason}\n\n"
            "<:NoNo:1525751848362049676> They have been renamed to **{penalty_name}** for **{duration} hours**.\n"
            "🔄 The count has been reset to **0**."
        ),
        (
            "[ALERT] SYSTEM_FAILSAFE_TRIGGERED. Node offline.\n"
            "{member} caused database corruption in {channel} at index **{streak}** during {reason}.\n\n"
            "🔒 Shame nickname **{penalty_name}** locked for **{duration} hours**.\n"
            "🔄 Flushing buffer to **0**."
        ),
        (
            "[SYS] DESTRUCT_SEQUENCE_COMPLETE.\n"
            "{member} dropped the packet at **{streak}** in {channel}! {reason}\n\n"
            "🏷️ Renamed to **{penalty_name}** ({duration} hours of containment).\n"
            "🔄 Resetting matrix to **0**."
        )
    ]

    SAVE_TEMPLATES = [
        "[SYS] SHIELD_TRIGGERED. {member} sequence deviation detected in {channel}: {reason}\n"
        "🛡️ **SAVE_TOKEN_CONSUMED.** Buffer integrity locked at index **{current}**.",
        "[SYS] IMPACT_ABSORBED. Shield absorbs hit from {member} in {channel} (Error: {reason}).\n"
        "🛡️ **SAVE_CONSUMED.** Sequence index **{current}** remains stable.",
        "[SYS] EMERGENCY_SHIELD_ONLINE. Failsafe activated for {member} in {channel} ({reason}).\n"
        "🛡️ **TOKEN_BURNED.** Streak defended. Resuming at **{current}**."
    ]

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=9384759384, force_registration=True)
        
        self.config.register_guild(
            channels={},  # dict of str(channel_id) -> channel config dict
            penalty_name="Count Loser",
            penalty_duration_hours=48,
            survivor_channels={},
            jackpot_vault=0,
            survivor_bankruptcy_percent=50,
            survivor_containment_hours=24,
            survivor_exile_hours=168,
            survivor_min_counts_req=100,
            survivor_license_fee=5000,
            containment_role_id=None,
            multiplier_enabled=True,
            base_reward=10,
            autoroles={} # dict of str(count_threshold) -> role_id
        )
        
        self.config.register_member(
            highest_progression=0,  # Tracks highest single number successfully counted
            original_nickname=None,
            penalty_end_time=None,
            survivor_exile_end=None,
            has_survivor_license=False,
            survivor_contributions=0,
            last_counted_streak_id=None,
            total_valid_counts=0,
            times_ruined=0
        )
        
        self.active_duels = {}
        self.duel_challenges = {}
        
        self.penalty_restorer.start()
        self.duel_timeout_checker.start()
        
        # Launch startup catch-up verification task
        self.bot.loop.create_task(self.catch_up_all_channels())

    def cog_unload(self):
        self.penalty_restorer.cancel()
        self.duel_timeout_checker.cancel()

    async def safe_react(self, message: discord.Message, emoji: str, fallback: str):
        try:
            await message.add_reaction(emoji)
        except Exception:
            try:
                await message.add_reaction(fallback)
            except Exception:
                pass

    def get_default_channel_config(self) -> dict:
        return {
            "current_count": 0,
            "last_counter_id": None,
            "high_score": 0,
            "saves": 0,
            "saves_enabled": True,
            "use_economy": False,
            "save_price": 5000,
            "milestones": {},
            "prestige_level": 0,
            "prestige_target": 10000,
        }

    # --- CORE GAMEPLAY ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        if message.channel.id in self.active_duels:
            await self.process_duel_message(message)
            return

        channels = await self.config.guild(message.guild).channels()
        ch_id_str = str(message.channel.id)
        if ch_id_str not in channels:
            return

        words = message.content.split()
        if not words:
            return
        first_word = words[0]
        parsed_number = evaluate_math(first_word)

        if parsed_number is None:
            return 

        await self.process_count(message, parsed_number)

    async def process_count(self, message: discord.Message, count_value: float):
        guild = message.guild
        author = message.author
        channel = message.channel
        ch_id_str = str(channel.id)

        # Check if Survivor channel
        survivor_channels = await self.config.guild(guild).survivor_channels()
        is_survivor = ch_id_str in survivor_channels

        if is_survivor:
            # 1. Active Exile Check
            exile_end = await self.config.member(author).survivor_exile_end()
            if exile_end and time.time() < exile_end:
                try:
                    await message.delete()
                except discord.Forbidden:
                    pass
                remaining = int(exile_end - time.time())
                hours = remaining // 3600
                minutes = (remaining % 3600) // 60
                await channel.send(
                    f"⚠️ {author.mention}, you are currently **exiled** from the Survivor node.\n"
                    f"Exile expires in: **{hours}h {minutes}m**.",
                    delete_after=5
                )
                return
                
            # 2. License Check
            fee = await self.config.guild(guild).survivor_license_fee()
            if fee > 0:
                has_license = await self.config.member(author).has_survivor_license()
                if not has_license:
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        pass
                    await channel.send(
                        f"⚠️ {author.mention}, a **Survivor License** is required to count here.\n"
                        f"Purchase one using `buysurvivorlicense` (Cost: {fee} credits).",
                        delete_after=5
                    )
                    return
                    
            # 3. Minimum progression check
            min_progression = await self.config.guild(guild).survivor_min_counts_req()
            if min_progression > 0:
                progression = await self.config.member(author).highest_progression()
                if progression < min_progression:
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        pass
                    await channel.send(
                        f"⚠️ {author.mention}, you need a highest progression score of at least **{min_progression}** to enter this node.\n"
                        f"Your current highest score is: **{progression}**.",
                        delete_after=5
                    )
                    return

        async with self.config.guild(guild).channels() as channels:
            if ch_id_str not in channels:
                return
            ch_data = channels[ch_id_str]

            current_count = ch_data.get("current_count", 0)
            last_counter_id = ch_data.get("last_counter_id")
            expected_number = current_count + 1

            if author.id == last_counter_id:
                await self.safe_react(message, "<:NoNo:1525751848362049676>", "❌")
                reason = random.choice(self.DOUBLE_COUNT_REASONS)
                await self.trigger_game_over_inside_lock(message, reason, channels)
                return

            if count_value != expected_number:
                await self.safe_react(message, "<:NoNo:1525751848362049676>", "❌")
                display_count = int(count_value) if count_value.is_integer() else count_value
                template = random.choice(self.WRONG_NUMBER_TEMPLATES)
                reason = template.format(expected=expected_number, got=display_count)
                await self.trigger_game_over_inside_lock(message, reason, channels)
                return

            # Success Path
            await self.safe_react(message, "<:approved:1525751752987508737>", "✅")
            if expected_number % 100 == 0:
                await self.safe_react(message, "<a:text_gif_oof61:1515093296710422640>", "💯")

            # Update stats: total valid counts
            valid_counts = await self.config.member(author).total_valid_counts()
            new_valid_counts = valid_counts + 1
            await self.config.member(author).total_valid_counts.set(new_valid_counts)

            # Check Milestone Auto-Roles
            guild_autoroles = await self.config.guild(guild).autoroles()
            if str(new_valid_counts) in guild_autoroles:
                role_id = guild_autoroles[str(new_valid_counts)]
                role = guild.get_role(role_id)
                if role:
                    try:
                        await author.add_roles(role, reason=f"Reached {new_valid_counts} total counts milestone!")
                        await channel.send(
                            f"🏆 **MILESTONE REWARD!** {author.mention} reached **{new_valid_counts}** total counts and unlocked the {role.mention} role!"
                        )
                    except discord.Forbidden:
                        pass

            # Streak Multiplier / Economy Reward
            multiplier_enabled = await self.config.guild(guild).multiplier_enabled()
            if multiplier_enabled:
                base = await self.config.guild(guild).base_reward()
                # Multiplier increases with streak depth (1x at 1-99, 2x at 100-199, etc.)
                multiplier = max(1, expected_number // 100 + 1)
                reward = int(base * multiplier)
                try:
                    await bank.deposit_credits(author, reward)
                except Exception:
                    pass

            # If Survivor channel, track contributions
            if is_survivor:
                streak_id = ch_data.get("streak_id")
                if not streak_id:
                    streak_id = str(random.randint(100000, 999999))
                    ch_data["streak_id"] = streak_id
                    
                user_streak_id = await self.config.member(author).last_counted_streak_id()
                if user_streak_id == streak_id:
                    contrib = await self.config.member(author).survivor_contributions()
                    await self.config.member(author).survivor_contributions.set(contrib + 1)
                else:
                    await self.config.member(author).last_counted_streak_id.set(streak_id)
                    await self.config.member(author).survivor_contributions.set(1)
                    
                contributors = ch_data.setdefault("contributors", [])
                if author.id not in contributors:
                    contributors.append(author.id)

            # Check Milestones
            milestones = ch_data.get("milestones", {})
            if str(expected_number) in milestones:
                if is_survivor:
                    await self.handle_survivor_milestone(message, expected_number, ch_data)
                else:
                    await self.handle_milestone(message, expected_number, milestones[str(expected_number)])

            # Update channel variables inside lock
            ch_data["current_count"] = expected_number
            ch_data["last_counter_id"] = author.id
            if expected_number > ch_data.get("high_score", 0):
                ch_data["high_score"] = expected_number
                
            # Update member highest progression
            member_highest = await self.config.member(author).highest_progression()
            if expected_number > member_highest:
                await self.config.member(author).highest_progression.set(expected_number)

        # Update member progression stats
        highest = await self.config.member(author).highest_progression()
        if expected_number > highest:
            await self.config.member(author).highest_progression.set(expected_number)

    async def handle_milestone(self, message: discord.Message, number: int, value: str):
        author = message.author
        value = str(value).strip()
        
        # 1. Local File Path in milestone directory or direct path
        import os
        local_dir = os.path.join(os.path.dirname(__file__), "milestones")
        possible_local = os.path.join(local_dir, value)
        file_to_send = possible_local if os.path.exists(possible_local) else (value if os.path.exists(value) else None)

        if file_to_send and os.path.isfile(file_to_send):
            try:
                d_file = discord.File(file_to_send)
                embed = discord.Embed(
                    title=f"🎉 **MILESTONE REACHED: {number}!** 🎉",
                    description=f"Awesome job, {author.mention}!",
                    color=0x9B59B6
                )
                embed.set_image(url=f"attachment://{os.path.basename(file_to_send)}")
                await message.reply(embed=embed, file=d_file)
                return
            except discord.HTTPException:
                pass

        # 2. URL Path -> Embed with image
        if value.startswith(("http://", "https://")):
            try:
                embed = discord.Embed(
                    title=f"🎉 **MILESTONE REACHED: {number}!** 🎉",
                    description=f"Awesome job, {author.mention}!",
                    color=0x9B59B6
                )
                embed.set_image(url=value)
                await message.reply(embed=embed)
            except discord.HTTPException:
                pass
        
        # 3. Sticker ID
        elif value.isdigit():
            sticker_id = int(value)
            if sticker_id != 0:
                try:
                    sticker = await self.bot.fetch_sticker(sticker_id)
                    await message.reply(
                        f"🎉 **MILESTONE REACHED: {number}!** 🎉\nAwesome job, {author.mention}!", 
                        stickers=[sticker]
                    )
                except discord.HTTPException:
                    pass

    async def trigger_game_over_inside_lock(self, message: discord.Message, reason: str, channels_dict: dict):
        guild = message.guild
        ch_id_str = str(message.channel.id)
        ch_data = channels_dict[ch_id_str]

        # Check if Survivor channel
        survivor_channels = await self.config.guild(guild).survivor_channels()
        is_survivor = ch_id_str in survivor_channels

        saves = ch_data.get("saves", 0)
        saves_enabled = ch_data.get("saves_enabled", True)

        # Bypass saves entirely in Survivor channels
        if not is_survivor and saves_enabled and saves > 0:
            ch_data["saves"] = saves - 1
            current_count = ch_data.get("current_count", 0)
            
            template = random.choice(self.SAVE_TEMPLATES)
            msg_text = template.format(
                member=message.author.mention,
                reason=reason,
                channel=message.channel.mention,
                current=current_count
            )
            await message.channel.send(msg_text)
            return

        # Game Over Flow
        streak = ch_data.get("current_count", 0)
        ch_data["current_count"] = 0
        ch_data["last_counter_id"] = None
        
        # Track ruined count statistic
        ruined = await self.config.member(message.author).times_ruined()
        await self.config.member(message.author).times_ruined.set(ruined + 1)
        
        if is_survivor:
            # Generate new streak_id to invalidate past contributions
            ch_data["streak_id"] = str(random.randint(100000, 999999))
            ch_data["contributors"] = []
            await self.apply_survivor_penalty(message.author, guild, streak, reason, message.channel)
        else:
            await self.apply_penalty(message.author, guild)

            duration = await self.config.guild(guild).penalty_duration_hours()
            penalty_name = await self.config.guild(guild).penalty_name()
            
            template = random.choice(self.GAME_OVER_TEMPLATES)
            description_text = template.format(
                member=message.author.mention,
                streak=streak,
                channel=message.channel.mention,
                reason=reason,
                penalty_name=penalty_name,
                duration=duration
            )
            
            embed = discord.Embed(
                title="<:NoNo:1525751848362049676> GAME OVER! <:NoNo:1525751848362049676>",
                description=description_text,
                color=discord.Color.red()
            )
            await message.channel.send(embed=embed)

    async def apply_survivor_penalty(self, author: discord.Member, guild: discord.Guild, streak: int, reason: str, channel: discord.TextChannel):
        # 1. Bankruptcy Fine
        bankruptcy_percent = await self.config.guild(guild).survivor_bankruptcy_percent()
        currency_name = "credits"
        try:
            balance = await bank.get_balance(author)
            currency_name = await bank.get_currency_name(guild)
        except Exception:
            balance = 0
            
        fine = int(balance * (bankruptcy_percent / 100)) if balance > 0 else 0
        if fine > 0:
            try:
                await bank.withdraw_credits(author, fine)
                vault = await self.config.guild(guild).jackpot_vault()
                await self.config.guild(guild).jackpot_vault.set(vault + fine)
            except Exception:
                fine = 0
                
        # 2. Exile Duration
        exile_hours = await self.config.guild(guild).survivor_exile_hours()
        exile_end = time.time() + (exile_hours * 3600)
        await self.config.member(author).survivor_exile_end.set(exile_end)
        
        # 3. Containment Lockout (Role)
        containment_role_id = await self.config.guild(guild).containment_role_id()
        containment_applied = False
        if containment_role_id:
            role = guild.get_role(containment_role_id)
            if role:
                try:
                    await author.add_roles(role, reason="Broke Survivor sequence.")
                    containment_applied = True
                except discord.Forbidden:
                    pass
                    
        # Apply name shaming as a fallback/additional penalty
        penalty_name = await self.config.guild(guild).penalty_name()
        if not await self.config.member(author).original_nickname():
            await self.config.member(author).original_nickname.set(author.display_name)
            
        containment_hours = await self.config.guild(guild).survivor_containment_hours()
        penalty_end = time.time() + (containment_hours * 3600)
        await self.config.member(author).penalty_end_time.set(penalty_end)
        
        try:
            # We use monospace helper to format their name as monospace shamed name
            shamed_nick = to_monospace(penalty_name)
            await author.edit(nick=shamed_nick, reason="Broke Survivor sequence.")
        except discord.Forbidden:
            pass
            
        # Post the hardcore Game Over message
        role_mention = f"<@&{containment_role_id}>" if containment_applied else "monospace shamed name"
        embed = discord.Embed(
            title="💀 SURVIVOR ELIMINATED! 💀",
            description=(
                f"{author.mention} broke the streak at **{streak}**!\n"
                f"**Reason**: {reason}\n\n"
                f"📉 **BANKRUPTCY**: Deducted **{fine} {currency_name}** ({bankruptcy_percent}% of balance) and added to the Jackpot Vault!\n"
                f"🔒 **CONTAINMENT**: Locked out of general chats for **{containment_hours} hours** (given {role_mention}).\n"
                f"🚫 **EXILE**: Banned from counting in the Survivor node for **{exile_hours} hours** (season ban)."
            ),
            color=discord.Color.dark_red()
        )
        await channel.send(embed=embed)
        try:
            await author.send(embed=embed)
        except Exception:
            pass

    async def apply_penalty(self, author: discord.Member, guild: discord.Guild):
        penalty_name = await self.config.guild(guild).penalty_name()
        duration_hours = await self.config.guild(guild).penalty_duration_hours()
        
        if not await self.config.member(author).original_nickname():
            await self.config.member(author).original_nickname.set(author.display_name)
            
        penalty_end = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=duration_hours)
        await self.config.member(author).penalty_end_time.set(penalty_end.timestamp())

        try:
            await author.edit(nick=penalty_name, reason="Broke the counting streak.")
        except discord.Forbidden:
            pass 

    # --- ANTI-TROLL LISTENERS ---
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild:
            return
            
        channels = await self.config.guild(after.guild).channels()
        ch_id_str = str(after.channel.id)
        if ch_id_str in channels:
            if before.content != after.content:
                if not before.content:
                    return
                words = before.content.split()
                if not words:
                    return
                first_word = words[0]
                if evaluate_math(first_word) is not None:
                    async with self.config.guild(after.guild).channels() as active_channels:
                        await self.trigger_game_over_inside_lock(
                            after, 
                            "[ERR_403_SNEAK] COVERT_EDIT_ATTEMPT: I saw that. Do not touch the buffer!", 
                            active_channels
                        )

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
            
        channels = await self.config.guild(message.guild).channels()
        ch_id_str = str(message.channel.id)
        if ch_id_str in channels:
            ch_data = channels[ch_id_str]
            last_counter = ch_data.get("last_counter_id")
            
            if message.author.id == last_counter:
                if not message.content:
                    return
                words = message.content.split()
                if not words:
                    return
                first_word = words[0]
                if evaluate_math(first_word) is not None:
                    async with self.config.guild(message.guild).channels() as active_channels:
                        await self.trigger_game_over_inside_lock(
                            message, 
                            "[WARN] NUMBER_DELETION_DETECTED. REASON: MALICIOUS_DECEPTION.", 
                            active_channels
                        )

    # --- BACKGROUND RESTORE TASK ---
    @tasks.loop(minutes=1.0)
    async def penalty_restorer(self):
        now = time.time()
        for guild in self.bot.guilds:
            containment_role_id = await self.config.guild(guild).containment_role_id()
            role = guild.get_role(containment_role_id) if containment_role_id else None
            
            member_data = await self.config.all_members(guild)
            for member_id, data in member_data.items():
                try:
                    member_id_int = int(member_id)
                except ValueError:
                    continue
                    
                member = guild.get_member(member_id_int)
                if not member:
                    try:
                        member = await guild.fetch_member(member_id_int)
                    except discord.HTTPException:
                        member = None
                        
                # 1. Nickname / Containment Role restore
                if data.get("penalty_end_time") and now >= data["penalty_end_time"]:
                    if member:
                        try:
                            await member.edit(nick=data.get("original_nickname"), reason="Counting penalty expired.")
                        except discord.Forbidden:
                            pass
                        if role:
                            try:
                                await member.remove_roles(role, reason="Counting penalty expired.")
                            except discord.Forbidden:
                                pass
                                
                    await self.config.member_from_ids(guild.id, member_id_int).penalty_end_time.clear()
                    await self.config.member_from_ids(guild.id, member_id_int).original_nickname.clear()
                    
                # 2. Survivor Exile restore
                if data.get("survivor_exile_end") and now >= data["survivor_exile_end"]:
                    await self.config.member_from_ids(guild.id, member_id_int).survivor_exile_end.clear()

    @penalty_restorer.before_loop
    async def before_penalty_restorer(self):
        await self.bot.wait_until_red_ready()

    # --- DUEL BACKGROUND TIMEOUT TASK ---
    @tasks.loop(seconds=1.0)
    async def duel_timeout_checker(self):
        now = time.time()
        to_delete = []
        for thread_id, duel in list(self.active_duels.items()):
            if duel["last_input_time"] is None:
                continue
            if now - duel["last_input_time"] > 5.0:
                to_delete.append((thread_id, duel))
                
        for thread_id, duel in to_delete:
            loser_id = duel["turn_user_id"]
            challenger = duel["challenger"]
            opponent = duel["opponent"]
            winner = opponent if loser_id == challenger.id else challenger
            loser = challenger if loser_id == challenger.id else opponent
            await self._end_duel(thread_id, winner, loser, "TIMEOUT")

    @duel_timeout_checker.before_loop
    async def before_duel_timeout_checker(self):
        await self.bot.wait_until_red_ready()

    # --- ADMIN CONFIGURATION COMMANDS ---
    @commands.hybrid_group(name="counting", aliases=["count", "c"])
    @commands.admin_or_permissions(manage_guild=True)
    async def counting(self, ctx: commands.Context):
        """Configure the multi-channel sequence game."""
        pass

    @commands.hybrid_command(name="counttop", aliases=["countingtop", "ctop"])
    @commands.guild_only()
    async def counttop(self, ctx: commands.Context):
        """View the server counting leaderboard (Total Counts, Highest Single, Ruined Streak, Accuracy)."""
        guild = ctx.guild
        member_data = await self.config.all_members(guild)
        
        if not member_data:
            return await ctx.send("No counting statistics recorded yet!")
            
        leaderboard = []
        for m_id, data in member_data.items():
            try:
                m_id_int = int(m_id)
            except ValueError:
                continue
            member = guild.get_member(m_id_int)
            name = member.display_name if member else f"User ({m_id})"
            
            valid = data.get("total_valid_counts", 0)
            highest = data.get("highest_progression", 0)
            ruined = data.get("times_ruined", 0)
            
            total_attempts = valid + ruined
            accuracy = (valid / total_attempts * 100) if total_attempts > 0 else 0.0
            
            if valid > 0 or highest > 0 or ruined > 0:
                leaderboard.append((name, valid, highest, ruined, accuracy))
                
        if not leaderboard:
            return await ctx.send("No counting activity logged yet.")
            
        # Sort by total valid counts descending
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        
        embed = discord.Embed(
            title="📊 **NETCOUNT SERVER LEADERBOARD** 📊",
            color=discord.Color.blue()
        )
        
        desc = ""
        for rank, (name, valid, highest, ruined, accuracy) in enumerate(leaderboard[:10], 1):
            desc += (
                f"**#{rank} {name}**\n"
                f"├ Total Counts: `{valid}` | Highest Single: `{highest}`\n"
                f"└ Times Ruined: `{ruined}` | Accuracy: `{accuracy:.1f}%`\n\n"
            )
            
        embed.description = desc
        await ctx.send(embed=embed)

    @counting.command(name="setmultiplier")
    async def setmultiplier(self, ctx: commands.Context, enabled: bool):
        """Enable or disable streak reward multipliers."""
        await self.config.guild(ctx.guild).multiplier_enabled.set(enabled)
        status = "ENABLED" if enabled else "DISABLED"
        await ctx.send(f"✅ Streak credit multiplier is now **{status}**.")

    @counting.command(name="setbasereward")
    async def setbasereward(self, ctx: commands.Context, amount: int):
        """Set base credit reward per valid count."""
        if amount < 0:
            return await ctx.send("Reward cannot be negative.")
        await self.config.guild(ctx.guild).base_reward.set(amount)
        await ctx.send(f"✅ Base credit reward per count set to **{amount}**.")

    @counting.command(name="addautorole")
    async def addautorole(self, ctx: commands.Context, total_counts: int, role: discord.Role):
        """Assign an auto-role unlocked when reaching a total count threshold."""
        if total_counts < 1:
            return await ctx.send("Count threshold must be at least 1.")
        async with self.config.guild(ctx.guild).autoroles() as autoroles:
            autoroles[str(total_counts)] = role.id
        await ctx.send(f"🏆 Milestone role {role.mention} set for reaching **{total_counts}** total valid counts!")

    @counting.command(name="removeautorole")
    async def removeautorole(self, ctx: commands.Context, total_counts: int):
        """Remove a milestone auto-role threshold."""
        async with self.config.guild(ctx.guild).autoroles() as autoroles:
            if str(total_counts) in autoroles:
                del autoroles[str(total_counts)]
                await ctx.send(f"🗑️ Removed auto-role milestone for **{total_counts}** counts.")
            else:
                await ctx.send("No auto-role configured for that threshold.")
        """Enable sequence game on a channel."""
        async with self.config.guild(ctx.guild).channels() as channels:
            ch_str = str(channel.id)
            if ch_str in channels:
                return await ctx.send(f"⚠️ {channel.mention} is already an active sequence channel.")
            channels[ch_str] = self.get_default_channel_config()
            
        await ctx.send(f"🌌 [SYS_INIT] SEQUENCE_PORT set to {channel.mention}. Listening for transmissions...")

    @counting.command(name="removechannel", aliases=["removec", "delchannel", "disable"])
    async def removechannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Deactivate sequence game on a channel and wipe its data."""
        async with self.config.guild(ctx.guild).channels() as channels:
            ch_str = str(channel.id)
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {channel.mention} is not registered as an active sequence channel.")
            del channels[ch_str]
            
        await ctx.send(f"🗑️ [SYS] Channel {channel.mention} sequence port deactivated and records purged.")

    @counting.command(name="addmilestone", aliases=["addm", "setmilestone"])
    async def addmilestone(self, ctx: commands.Context, number: int, value: str, channel: Optional[discord.TextChannel] = None):
        """
        Assign a milestone action inside a channel.
        Usage: [p]counting addmilestone <number> <value> [channel]
        """
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            channels[ch_str]["milestones"][str(number)] = value
            
        await ctx.send(f"<:approved:1525751752987508737> [SYS] Milestone **{number}** routed to `{value}` in {target_channel.mention}.")

    @counting.command(name="viewmilestones", aliases=["viewm", "milestones", "showmilestones"])
    async def viewmilestones(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """View all registered milestones for a channel."""
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        channels = await self.config.guild(ctx.guild).channels()
        if ch_str not in channels:
            return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            
        milestones = channels[ch_str].get("milestones", {})
        if not milestones:
            return await ctx.send(f"No milestones configured in {target_channel.mention}.")
            
        msg = f"__**Active Milestones inside {target_channel.mention}**__\n"
        for num, val in sorted(milestones.items(), key=lambda x: int(x[0])):
            type_str = f"Sticker/ID: `{val}`" if val.isdigit() else f"URL: `{val}`"
            msg += f"• **{num}** -> {type_str}\n"
            
        from redbot.core.utils.chat_formatting import pagify
        for page in pagify(msg):
            await ctx.send(page)

    @counting.command(name="removemilestone", aliases=["removem", "delmilestone"])
    async def removemilestone(self, ctx: commands.Context, number: int, channel: Optional[discord.TextChannel] = None):
        """Remove a milestone from a channel."""
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            milestones = channels[ch_str].get("milestones", {})
            if str(number) in milestones:
                del milestones[str(number)]
                await ctx.send(f"🗑️ [SYS] Milestone **{number}** offline in {target_channel.mention}.")
            else:
                await ctx.send("⚠️ Beacon milestone not found in config records.")

    @counting.command(name="togglesaves", aliases=["togglesave", "ts"])
    async def togglesaves(self, ctx: commands.Context, toggle: bool, channel: Optional[discord.TextChannel] = None):
        """Enable or disable saves for a channel."""
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            channels[ch_str]["saves_enabled"] = toggle
            
        status = "ENABLED" if toggle else "DISABLED"
        await ctx.send(f"🛡️ [SYS] Save tokens are now **{status}** in {target_channel.mention}.")

    @counting.command(name="addsave", aliases=["givesave", "as"])
    async def addsave(self, ctx: commands.Context, amount: int = 1, channel: Optional[discord.TextChannel] = None):
        """Add a save token to protect the streak in a channel."""
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            current = channels[ch_str].get("saves", 0)
            channels[ch_str]["saves"] = current + amount
            new_amount = current + amount
            
        await ctx.send(f"<:approved:1525751752987508737> [SYS] SHIELD_RECHARGED: +{amount} save token(s) in {target_channel.mention}. Capacity: **{new_amount}**.")

    @counting.command(name="setcount", aliases=["setc", "setvalue", "override"])
    async def setcount(self, ctx: commands.Context, count: int, channel: Optional[discord.TextChannel] = None):
        """Manually override the current count in a channel."""
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            channels[ch_str]["current_count"] = count
            channels[ch_str]["last_counter_id"] = None
            
        await ctx.send(f"🛠️ [SYS_OVERRIDE] BUFFER_REALIGNED in {target_channel.mention} to count **{count}**. Listening for **{count + 1}**.")

    @counting.command(name="resetloss", aliases=["clearpenalties", "clearshame", "resetpenalties"])
    async def resetloss(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """Reset loss data / shame penalties so members stay in positive standing."""
        guild = ctx.guild
        if member:
            await self.config.member(member).penalty_end_time.clear()
            await self.config.member(member).original_nickname.clear()
            await self.config.member(member).survivor_exile_end.clear()
            try:
                orig_name = await self.config.member(member).original_nickname() or member.display_name
                await member.edit(nick=orig_name, reason="Loss data reset by admin.")
            except discord.Forbidden:
                pass
            await ctx.send(f"✅ Loss data and shame penalties cleared for {member.mention}.")
        else:
            member_data = await self.config.all_members(guild)
            for m_id in member_data.keys():
                try:
                    m_id_int = int(m_id)
                    await self.config.member_from_ids(guild.id, m_id_int).penalty_end_time.clear()
                    await self.config.member_from_ids(guild.id, m_id_int).original_nickname.clear()
                    await self.config.member_from_ids(guild.id, m_id_int).survivor_exile_end.clear()
                except Exception:
                    pass
            await ctx.send("✅ [SYS] All server loss data and shame penalties purged. Everyone is in positive standing!")

    @counting.command(name="reseteco", aliases=["cleareco", "reseteconomy"])
    async def reseteco(self, ctx: commands.Context):
        """Clear netcount economy data (jackpot vault and survivor license records)."""
        guild = ctx.guild
        await self.config.guild(guild).jackpot_vault.set(0)
        member_data = await self.config.all_members(guild)
        for m_id in member_data.keys():
            try:
                m_id_int = int(m_id)
                await self.config.member_from_ids(guild.id, m_id_int).has_survivor_license.set(False)
                await self.config.member_from_ids(guild.id, m_id_int).survivor_contributions.set(0)
            except Exception:
                pass
        await ctx.send("💰 [SYS] Netcount economy cleared! Jackpot vault reset to 0 and all licenses wiped.")

    @counting.command(name="prestigetarget", aliases=["ptarget", "pt"])
    async def prestigetarget(self, ctx: commands.Context, target: int, channel: Optional[discord.TextChannel] = None):
        """Set the prestige target for a channel."""
        if target < 100:
            return await ctx.send("[ERR] Target must be at least 100 counts.")
            
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            channels[ch_str]["prestige_target"] = target
            
        await ctx.send(f"🎯 [SYS] Prestige threshold locked at **{target}** for {target_channel.mention}.")

    @counting.command(name="prestige", aliases=["ascend", "p"])
    async def prestige(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Cash in a massive streak to prestige in a channel."""
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            
            ch_data = channels[ch_str]
            current_count = ch_data.get("current_count", 0)
            target = ch_data.get("prestige_target", 10000)
            
            if current_count < target:
                return await ctx.send(f"<:NoNo:1525751848362049676> [SYS_BLOCKED] Core charge: {current_count}/{target} in {target_channel.mention}.")

            current_level = ch_data.get("prestige_level", 0)
            new_level = current_level + 1
            
            ch_data["current_count"] = 0
            ch_data["last_counter_id"] = None
            ch_data["prestige_level"] = new_level

        embed = discord.Embed(
            title="🌌 [SYS] ASCENSION_SEQUENCE_COMPLETE 🌌",
            description=(
                f"**CORE INTEGRITY RETROFITTED:** {target_channel.mention} exceeded **{target}** counts!\n\n"
                f"🔄 Buffer cache flushed to **0**.\n"
                f"📈 Node upgraded to **Prestige Rank {new_level}**."
            ),
            color=discord.Color.purple()
        )
        embed.set_image(url="https://media.giphy.com/media/26tOZ42Mg6pbTUPHW/giphy.gif")
        await ctx.send(embed=embed)

    @counting.command(name="economy", aliases=["toggleeconomy", "eco"])
    async def economy(self, ctx: commands.Context, toggle: bool, channel: Optional[discord.TextChannel] = None):
        """Enable or disable economy features in a channel."""
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            channels[ch_str]["use_economy"] = toggle
            
        status = "ONLINE" if toggle else "OFFLINE"
        await ctx.send(f"<:approved:1525751752987508737> [SYS] Economy integration in {target_channel.mention} set to: **{status}**")

    @counting.command(name="saveprice", aliases=["setprice", "price"])
    async def saveprice(self, ctx: commands.Context, price: int, channel: Optional[discord.TextChannel] = None):
        """Set the credit cost to buy a save token in a channel."""
        if price < 1:
            return await ctx.send("[ERR] Price must be at least 1 credit.")
            
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        
        async with self.config.guild(ctx.guild).channels() as channels:
            if ch_str not in channels:
                return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            channels[ch_str]["save_price"] = price
            
        currency_name = await bank.get_currency_name(ctx.guild)
        await ctx.send(f"<:approved:1525751752987508737> [SYS] Save price in {target_channel.mention} updated to: **{price} {currency_name}**")

    @counting.command(name="penaltyname", aliases=["pname", "setpenaltyname"])
    async def penaltyname(self, ctx: commands.Context, *, name: str):
        """Set the nickname given to users who break a streak (Server-Wide)."""
        if len(name) > 32:
            return await ctx.send("[ERR] Shame tag exceeds 32 characters.")
        await self.config.guild(ctx.guild).penalty_name.set(name)
        await ctx.send(f"[SYS] Server-Wide SHAME_TAG registered as: **{name}**")

    @counting.command(name="duration", aliases=["pduration", "setduration"])
    async def duration(self, ctx: commands.Context, hours: int):
        """Set how many hours nickname penalties last (Server-Wide)."""
        if hours < 1:
            return await ctx.send("[ERR] Duration must be at least 1 hour.")
        await self.config.guild(ctx.guild).penalty_duration_hours.set(hours)
        await ctx.send(f"[SYS] Server-Wide SHAME_CONTAINMENT_LOCK set to **{hours} hours**.")

    @counting.command(name="pardon", aliases=["unshame", "unpenalize", "clearpenalty"])
    async def pardon(self, ctx: commands.Context, member: discord.Member):
        """Pardon a player early, removing their shamed nickname, containment role, and exile."""
        guild = ctx.guild
        data = await self.config.member(member).all()
        
        orig_nick = data.get("original_nickname")
        try:
            await member.edit(nick=orig_nick, reason="Admin pardon.")
        except discord.Forbidden:
            pass
            
        containment_role_id = await self.config.guild(guild).containment_role_id()
        if containment_role_id:
            role = guild.get_role(containment_role_id)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Admin pardon.")
                except discord.Forbidden:
                    pass
                    
        await self.config.member(member).penalty_end_time.clear()
        await self.config.member(member).original_nickname.clear()
        await self.config.member(member).survivor_exile_end.clear()
        
        await ctx.send(f"✅ **PARDON GRANTED:** {member.mention} has been released from shaming containment and survivor exile.")

    @counting.command(name="recount", aliases=["catchup", "resync"])
    async def recount(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Force the bot to scan history and recount/catchup messages in the channel."""
        target_channel = channel or ctx.channel
        guild = ctx.guild
        ch_str = str(target_channel.id)
        
        channels = await self.config.guild(guild).channels()
        if ch_str not in channels:
            return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            
        await ctx.send(f"🔄 **RECOUNT INITIATED:** Scanning last 100 messages in {target_channel.mention}...")
        
        ch_data = channels[ch_str]
        try:
            history = [msg async for msg in target_channel.history(limit=100, oldest_first=False)]
        except Exception as e:
            return await ctx.send(f"❌ Failed to read channel history: {str(e)}")
            
        if not history:
            return await ctx.send("⚠️ No messages found in history.")
            
        history.reverse()
        
        current_count = ch_data.get("current_count", 0)
        last_counter_id = ch_data.get("last_counter_id")
        survivor_channels = await self.config.guild(guild).survivor_channels()
        is_survivor = ch_str in survivor_channels
        
        updated_count = current_count
        updated_last_counter = last_counter_id
        failed = False
        fail_msg = None
        fail_reason = None
        
        for msg in history:
            if msg.author.bot:
                continue
                
            words = msg.content.split()
            if not words:
                continue
                
            parsed = evaluate_math(words[0])
            if parsed is None:
                continue
                
            if parsed <= updated_count:
                continue
            elif parsed == updated_count + 1:
                if msg.author.id == updated_last_counter:
                    failed = True
                    fail_msg = msg
                    fail_reason = random.choice(self.DOUBLE_COUNT_REASONS)
                    break
                updated_count = parsed
                updated_last_counter = msg.author.id
                
                await self.safe_react(msg, "<:approved:1525751752987508737>", "✅")
                if int(updated_count) % 100 == 0:
                    await self.safe_react(msg, "<a:text_gif_oof61:1515093296710422640>", "💯")
                    
                member_highest = await self.config.member(msg.author).highest_progression()
                if updated_count > member_highest:
                    await self.config.member(msg.author).highest_progression.set(int(updated_count))
                    
                if is_survivor:
                    streak_id = ch_data.get("streak_id")
                    if streak_id:
                        user_streak_id = await self.config.member(msg.author).last_counted_streak_id()
                        if user_streak_id == streak_id:
                            contrib = await self.config.member(msg.author).survivor_contributions()
                            await self.config.member(msg.author).survivor_contributions.set(contrib + 1)
                        else:
                            await self.config.member(msg.author).last_counted_streak_id.set(streak_id)
                            await self.config.member(msg.author).survivor_contributions.set(1)
                        
                        contributors = ch_data.setdefault("contributors", [])
                        if msg.author.id not in contributors:
                            contributors.append(msg.author.id)
            else:
                failed = True
                fail_msg = msg
                display_count = int(parsed) if parsed.is_integer() else parsed
                template = random.choice(self.WRONG_NUMBER_TEMPLATES)
                fail_reason = template.format(expected=int(updated_count + 1), got=display_count)
                break
                
        if failed:
            async with self.config.guild(guild).channels() as active_channels:
                ch_data["current_count"] = 0
                ch_data["last_counter_id"] = None
                if is_survivor:
                    ch_data["streak_id"] = str(random.randint(100000, 999999))
                    ch_data["contributors"] = []
                active_channels[ch_str] = ch_data
                
            if is_survivor:
                await self.apply_survivor_penalty(fail_msg.author, guild, int(updated_count), fail_reason, target_channel)
            else:
                await self.apply_penalty(fail_msg.author, guild)
                
                duration = await self.config.guild(guild).penalty_duration_hours()
                penalty_name = await self.config.guild(guild).penalty_name()
                template = random.choice(self.GAME_OVER_TEMPLATES)
                description_text = template.format(
                    member=fail_msg.author.mention,
                    streak=int(updated_count),
                    channel=target_channel.mention,
                    reason=fail_reason,
                    penalty_name=penalty_name,
                    duration=duration
                )
                
                embed = discord.Embed(
                    title="<:NoNo:1525751848362049676> RETROACTIVE GAME OVER! <:NoNo:1525751848362049676>",
                    description=f"An error occurred or was caught during recount:\n\n{description_text}",
                    color=discord.Color.red()
                )
                await target_channel.send(embed=embed)
        else:
            if updated_count > current_count:
                async with self.config.guild(guild).channels() as active_channels:
                    active_channels[ch_str]["current_count"] = int(updated_count)
                    active_channels[ch_str]["last_counter_id"] = updated_last_counter
                    if updated_count > active_channels[ch_str].get("high_score", 0):
                        active_channels[ch_str]["high_score"] = int(updated_count)
                
                diff = int(updated_count - current_count)
                await ctx.send(f"✅ **RECOUNT COMPLETE:** Caught up **{diff}** counts. Current Index is now **{int(updated_count)}**.")
            else:
                await ctx.send("ℹ️ **RECOUNT COMPLETE:** Database count is already fully synchronized with channel history. No new counts detected.")

    # --- LEADERBOARD & USER COMMANDS ---
    @commands.hybrid_command(name="countlb", aliases=["clb", "scoreboard"])
    async def countlb(self, ctx: commands.Context):
        """View the sequence progression leaderboard (Highest single counts)."""
        members = await self.config.all_members(ctx.guild)
        if not members:
            return await ctx.send("[ERR] Database record is empty. No telemetry detected.")

        sorted_members = sorted(
            members.items(), 
            key=lambda x: x[1].get('highest_progression', 0), 
            reverse=True
        )
        
        lb_text = ""
        for index, (member_id, data) in enumerate(sorted_members[:10], start=1):
            member = ctx.guild.get_member(member_id)
            name = member.display_name if member else f"Unknown User ({member_id})"
            progression = data.get('highest_progression', 0)
            lb_text += f"**{index}.** {name} — Highest progression: **{progression}**\n"

        embed = discord.Embed(
            title="🏆 Telemetry: Highest Count Progression", 
            description=lb_text, 
            color=discord.Color.gold()
        )
        
        # Display peak info for the current channel, if active
        channels = await self.config.guild(ctx.guild).channels()
        ch_str = str(ctx.channel.id)
        if ch_str in channels:
            ch_data = channels[ch_str]
            embed.set_footer(
                text=f"Channel High Score: {ch_data.get('high_score', 0)} | Prestige Level: {ch_data.get('prestige_level', 0)}"
            )
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="buysave", aliases=["bs"])
    @commands.guild_only()
    async def buysave(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Buy a save token for a specific channel using your server credits."""
        target_channel = channel or ctx.channel
        ch_str = str(target_channel.id)
        guild = ctx.guild
        
        channels = await self.config.guild(guild).channels()
        if ch_str not in channels:
            return await ctx.send(f"⚠️ {target_channel.mention} is not an active sequence channel.")
            
        ch_data = channels[ch_str]
        use_eco = ch_data.get("use_economy", False)
        if not use_eco:
            return await ctx.send(f"[ERR] Economy integration is offline in {target_channel.mention}.")
        
        price = ch_data.get("save_price", 5000)
        try:
            balance = await bank.get_balance(ctx.author)
        except Exception:
            return await ctx.send("[ERR] Bank protocol error. Check bank configuration.")
            
        if balance < price:
            currency_name = await bank.get_currency_name(guild)
            return await ctx.send(f"[ERR] Insufficient funds. You need **{price} {currency_name}**, but only have **{balance}**.")
            
        try:
            await bank.withdraw_credits(ctx.author, price)
        except ValueError:
            currency_name = await bank.get_currency_name(guild)
            return await ctx.send(f"[ERR] Transaction aborted. You need **{price} {currency_name}**.")
            
        async with self.config.guild(guild).channels() as active_channels:
            active_channels[ch_str]["saves"] = active_channels[ch_str].get("saves", 0) + 1
            new_save_count = active_channels[ch_str]["saves"]
            
        currency_name = await bank.get_currency_name(guild)
        await ctx.send(
            f"<:approved:1525751752987508737> [SYS] TRANSACTION_COMPLETE: Deducted **{price} {currency_name}** from {ctx.author.mention}.\n"
            f"🛡️ **SHIELD_RECHARGED.** Added 1 save token to {target_channel.mention}. Current capacity: **{new_save_count}**."
        )

    # --- DUEL CORE LOGIC ---
    def _get_other_player(self, duel, player: discord.Member) -> discord.Member:
        if player.id == duel["challenger"].id:
            return duel["opponent"]
        return duel["challenger"]

    async def process_duel_message(self, message: discord.Message):
        thread_id = message.channel.id
        duel = self.active_duels.get(thread_id)
        if not duel:
            return
            
        author = message.author
        if author.id not in [duel["challenger"].id, duel["opponent"].id]:
            return
            
        if author.id != duel["turn_user_id"]:
            await self._end_duel(thread_id, winner=self._get_other_player(duel, author), loser=author, reason="DOUBLE_COUNT")
            return
            
        words = message.content.split()
        if not words:
            return
            
        parsed_number = evaluate_math(words[0])
        if parsed_number is None:
            return  # Allow standard chatting without penalty
            
        expected = duel["expected"]
        if parsed_number != expected:
            await self._end_duel(thread_id, winner=self._get_other_player(duel, author), loser=author, reason="WRONG_NUMBER")
            return
            
        # Update duel state
        duel["current_count"] = expected
        duel["expected"] = expected + 1
        duel["turn_user_id"] = self._get_other_player(duel, author).id
        duel["last_input_time"] = time.time()
        
        await self.safe_react(message, "<:approved:1525751752987508737>", "✅")

    async def _end_duel(self, thread_id: int, winner: discord.Member, loser: discord.Member, reason: str):
        if thread_id not in self.active_duels:
            return
            
        duel = self.active_duels.pop(thread_id)
        wager = duel["wager"]
        current_count = duel["current_count"]
        guild = winner.guild
        thread = guild.get_thread(thread_id)
        
        tax = int(wager * 2 * 0.05) if wager > 0 else 0
        winnings = (wager * 2) - tax
        
        currency_name = "credits"
        try:
            currency_name = await bank.get_currency_name(guild)
        except Exception:
            pass
            
        if wager > 0:
            try:
                # Credit the winnings to the winner. Both players already paid the wager at accept-time.
                await bank.deposit_credits(winner, winnings)
                payout_text = f"💸 **WAGER SETTLED:** {winner.mention} wins **{winnings} {currency_name}** (includes the pot minus 5% server tax)."
            except Exception:
                payout_text = "⚠️ [ERR] Failed to deposit winnings to the bank."
        else:
            payout_text = "🤝 No credits were wagered in this duel."
            
        if reason == "TIMEOUT":
            outcome_msg = f"⏱️ **TIME'S UP!** {loser.mention} failed to count within 5 seconds!"
        elif reason == "WRONG_NUMBER":
            outcome_msg = f"❌ **WRONG NUMBER!** {loser.mention} broke the sequence!"
        elif reason == "DOUBLE_COUNT":
            outcome_msg = f"🚫 **DOUBLE COUNT!** {loser.mention} counted twice in a row!"
        else:
            outcome_msg = f"🏳️ **DUEL ENDED:** {loser.mention} forfeited."
            
        summary = (
            f"⚡ **DUEL COMPLETE** ⚡\n"
            f"{outcome_msg}\n"
            f"🏆 **Winner:** {winner.mention}\n"
            f"📈 **Final Count Reached:** **{current_count}**\n\n"
            f"{payout_text}\n"
            f"🔒 *This thread will be deleted in 10 seconds.*"
        )
        
        if thread:
            try:
                await thread.send(summary)
            except Exception:
                pass
                
        parent_channel = thread.parent if thread else None
        if parent_channel:
            try:
                await parent_channel.send(
                    f"⚔️ **DUEL RESULT:** {winner.mention} has defeated {loser.mention} in a sequence duel! Final count reached: **{current_count}**."
                )
            except Exception:
                pass
                
        await asyncio.sleep(10)
        if thread:
            try:
                await thread.delete()
            except Exception:
                pass

    # --- DUEL USER COMMANDS ---
    @commands.hybrid_group(name="cduel")
    @commands.guild_only()
    async def cduel(self, ctx: commands.Context):
        """PvP sequence counting duels with wagers."""
        pass

    @cduel.command(name="challenge")
    async def challenge(self, ctx: commands.Context, opponent: discord.Member, wager: int = 0):
        """Challenge another player to a counting duel with optional wager."""
        challenger = ctx.author
        guild = ctx.guild
        
        if opponent.bot:
            return await ctx.send("⚠️ You cannot challenge bots.")
        if opponent.id == challenger.id:
            return await ctx.send("⚠️ You cannot challenge yourself.")
        if wager < 0:
            return await ctx.send("⚠️ Wager must be a positive number.")
            
        # Verify challenger has funds
        if wager > 0:
            try:
                balance = await bank.get_balance(challenger)
                if balance < wager:
                    currency_name = await bank.get_currency_name(guild)
                    return await ctx.send(f"⚠️ Insufficient funds. You need **{wager} {currency_name}** to wager.")
            except Exception:
                return await ctx.send("⚠️ Bank integration is currently offline.")
                
        guild_id = guild.id
        if guild_id not in self.duel_challenges:
            self.duel_challenges[guild_id] = {}
            
        self.duel_challenges[guild_id][opponent.id] = {
            "challenger": challenger,
            "wager": wager,
            "time": time.time()
        }
        
        currency_name = "credits"
        try:
            currency_name = await bank.get_currency_name(guild)
        except Exception:
            pass
            
        wager_text = f" with a wager of **{wager} {currency_name}**" if wager > 0 else ""
        await ctx.send(
            f"⚔️ {challenger.mention} has challenged {opponent.mention} to a sequence counting duel{wager_text}!\n"
            f"Type `{ctx.clean_prefix}cduel accept` to begin or `{ctx.clean_prefix}cduel decline` to reject."
        )

    @cduel.command(name="accept")
    async def accept(self, ctx: commands.Context):
        """Accept an incoming counting duel challenge."""
        opponent = ctx.author
        guild = ctx.guild
        guild_id = guild.id
        
        if guild_id not in self.duel_challenges or opponent.id not in self.duel_challenges[guild_id]:
            return await ctx.send("⚠️ You have no active pending challenges.")
            
        challenge_data = self.duel_challenges[guild_id].pop(opponent.id)
        challenger = challenge_data["challenger"]
        wager = challenge_data["wager"]
        
        # Verify both players still exist in the guild
        challenger_member = guild.get_member(challenger.id)
        if not challenger_member:
            return await ctx.send("⚠️ Challenger has left the server.")
            
        # Verify both still have funds and deduct wagers immediately
        currency_name = "credits"
        try:
            currency_name = await bank.get_currency_name(guild)
        except Exception:
            pass
            
        if wager > 0:
            try:
                c_bal = await bank.get_balance(challenger_member)
                o_bal = await bank.get_balance(opponent)
                
                if c_bal < wager:
                    return await ctx.send(f"⚠️ Challenger {challenger_member.mention} no longer has enough credits.")
                if o_bal < wager:
                    return await ctx.send(f"⚠️ You do not have enough credits to cover the wager of **{wager} {currency_name}**.")
                    
                # Deduct from both
                await bank.withdraw_credits(challenger_member, wager)
                await bank.withdraw_credits(opponent, wager)
            except Exception:
                return await ctx.send("⚠️ Failed to process wager deduction. Duel aborted.")
                
        # Create temporary thread
        try:
            thread = await ctx.channel.create_thread(
                name=f"⚡-duel-{challenger_member.name}-vs-{opponent.name}",
                auto_archive_duration=60,
                type=discord.ChannelType.public_thread
            )
        except Exception as e:
            # Refund if thread creation fails
            if wager > 0:
                try:
                    await bank.deposit_credits(challenger_member, wager)
                    await bank.deposit_credits(opponent, wager)
                except Exception:
                    pass
            return await ctx.send(f"⚠️ Failed to create duel arena thread: {str(e)}")
            
        # Setup duel session state
        self.active_duels[thread.id] = {
            "challenger": challenger_member,
            "opponent": opponent,
            "wager": wager,
            "current_count": 0,
            "expected": 1,
            "turn_user_id": challenger_member.id,
            "last_input_time": None
        }
        
        await ctx.send(f"⚔️ **Duel Arena open!** Move to {thread.mention} to start the battle.")
        
        await thread.send(
            f"⚔️ **DUEL INITIATED!** ⚔️\n"
            f"Combatants: {challenger_member.mention} vs {opponent.mention}\n"
            f"Wager: **{wager} {currency_name}** (credits locked)\n\n"
            f"📖 **Rules:**\n"
            f"1. Alternate counting starting at **1** (math like `0+1` is allowed).\n"
            f"2. You have **5 seconds** per turn (starts after the first count is sent).\n"
            f"3. First turn belongs to challenger {challenger_member.mention}.\n"
            f"4. Wrong numbers, double counts, or timeouts = instant loss!\n\n"
            f"🏁 {challenger_member.mention}, count **1** to begin (no timer active yet)!"
        )

    @cduel.command(name="decline")
    async def decline(self, ctx: commands.Context):
        """Decline an incoming counting duel challenge."""
        opponent = ctx.author
        guild = ctx.guild
        guild_id = guild.id
        
        if guild_id not in self.duel_challenges or opponent.id not in self.duel_challenges[guild_id]:
            return await ctx.send("⚠️ You have no active pending challenges.")
            
        challenge_data = self.duel_challenges[guild_id].pop(opponent.id)
        challenger = challenge_data["challenger"]
        
        await ctx.send(f"🏳️ {opponent.mention} has declined the duel challenge from {challenger.mention}.")

    @cduel.command(name="status")
    async def status(self, ctx: commands.Context):
        """View the active duels in this server."""
        active = []
        for thread_id, duel in self.active_duels.items():
            if duel["challenger"].guild.id == ctx.guild.id:
                active.append(f"- {duel['challenger'].mention} vs {duel['opponent'].mention} (Count: **{duel['current_count']}**)")
                
        if not active:
            await ctx.send("📡 No active counting duels running on this server currently.")
        else:
            await ctx.send("⚔️ **Active Counting Duels:**\n" + "\n".join(active))

    # --- SURVIVOR CORE LOGIC ---
    async def handle_survivor_milestone(self, message: discord.Message, number: int, ch_data: dict):
        guild = message.guild
        vault = await self.config.guild(guild).jackpot_vault()
        contributors = ch_data.get("contributors", [])
        
        # Verify there is credit in vault and contributors
        if vault > 0 and contributors:
            # Fetch contributions for each active player
            contrib_map = {}
            total_contrib = 0
            for user_id in contributors:
                contrib = await self.config.member_from_ids(guild.id, user_id).survivor_contributions()
                if contrib > 0:
                    contrib_map[user_id] = contrib
                    total_contrib += contrib
                    
            if total_contrib > 0:
                payout_list = []
                for user_id, count in contrib_map.items():
                    payout = int(vault * (count / total_contrib))
                    if payout > 0:
                        member = guild.get_member(user_id)
                        if not member:
                            try:
                                member = await guild.fetch_member(user_id)
                            except discord.HTTPException:
                                pass
                        if member:
                            try:
                                await bank.deposit_credits(member, payout)
                                payout_list.append(f"- {member.mention}: received **{payout}** credits (contributed **{count}** numbers).")
                            except Exception:
                                pass
                                
                currency_name = "credits"
                try:
                    currency_name = await bank.get_currency_name(guild)
                except Exception:
                    pass
                    
                # Reset vault & contributions
                await self.config.guild(guild).jackpot_vault.set(0)
                
                # Setup new streak ID
                ch_data["streak_id"] = str(random.randint(100000, 999999))
                ch_data["contributors"] = []
                
                payout_str = "\n".join(payout_list) if payout_list else "None."
                embed = discord.Embed(
                    title=f"🏆 SURVIVOR MILESTONE REACHED: {number}! 🏆",
                    description=(
                        f"Sequence node successfully defended!\n\n"
                        f"💰 **Jackpot Distributed**: Split **{vault} {currency_name}** among active contributors:\n"
                        f"{payout_str}\n\n"
                        f"🔄 Contributions reset. Decryption streak continues!"
                    ),
                    color=discord.Color.gold()
                )
                await message.channel.send(embed=embed)

    # --- USER SURVIVOR LICENSE COMMAND ---
    @commands.hybrid_command(name="buysurvivorlicense", aliases=["buysurv"])
    @commands.guild_only()
    async def buysurvivorlicense(self, ctx: commands.Context):
        """Buy a lifetime Survivor License to participate in Survivor channels."""
        guild = ctx.guild
        author = ctx.author
        
        has_lic = await self.config.member(author).has_survivor_license()
        if has_lic:
            return await ctx.send("ℹ️ You already own a Survivor License.")
            
        fee = await self.config.guild(guild).survivor_license_fee()
        if fee <= 0:
            return await ctx.send("ℹ️ Survivor Licenses are currently free or disabled on this server.")
            
        try:
            balance = await bank.get_balance(author)
        except Exception:
            return await ctx.send("⚠️ Bank integration is currently offline.")
            
        if balance < fee:
            currency_name = await bank.get_currency_name(guild)
            return await ctx.send(f"❌ Insufficient funds. You need **{fee} {currency_name}** to purchase a license.")
            
        try:
            await bank.withdraw_credits(author, fee)
            await self.config.member(author).has_survivor_license.set(True)
        except Exception:
            return await ctx.send("⚠️ Failed to process credit transaction.")
            
        currency_name = await bank.get_currency_name(guild)
        await ctx.send(
            f"✅ **TRANSACTION COMPLETE:** Purchased a Survivor License for **{fee} {currency_name}**!\n"
            f"You are now cleared for entry in all Survivor sequence channels."
        )

    # --- ADMIN SURVIVOR CONFIG COMMANDS ---
    @counting.group(name="survivor")
    async def survivor(self, ctx: commands.Context):
        """Configure Survivor Mode settings."""
        pass

    @survivor.command(name="addchannel")
    async def surv_addchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Enable Survivor rules on a text channel."""
        guild = ctx.guild
        ch_str = str(channel.id)
        
        # Make sure it's an active counting channel
        channels = await self.config.guild(guild).channels()
        if ch_str not in channels:
            # Add to channels config automatically
            async with self.config.guild(guild).channels() as active_channels:
                active_channels[ch_str] = self.get_default_channel_config()
                
        async with self.config.guild(guild).survivor_channels() as surv_channels:
            if ch_str in surv_channels:
                return await ctx.send(f"⚠️ {channel.mention} already has Survivor rules active.")
            surv_channels[ch_str] = True
            
        # Update streak ID to initialize
        async with self.config.guild(guild).channels() as active_channels:
            active_channels[ch_str]["streak_id"] = str(random.randint(100000, 999999))
            active_channels[ch_str]["contributors"] = []
            
        await ctx.send(f"💀 **SURVIVOR PROTOCOL RECON**: {channel.mention} is now a hardcore Survivor channel. No saves allowed.")

    @survivor.command(name="removechannel")
    async def surv_removechannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Disable Survivor rules on a text channel."""
        guild = ctx.guild
        ch_str = str(channel.id)
        
        async with self.config.guild(guild).survivor_channels() as surv_channels:
            if ch_str not in surv_channels:
                return await ctx.send(f"⚠️ {channel.mention} is not running Survivor rules.")
            surv_channels.pop(ch_str)
            
        await ctx.send(f"✅ **SURVIVOR PROTOCOL OFFLINE**: {channel.mention} reverted to standard counting rules.")

    @survivor.command(name="setbankruptcy")
    async def surv_setbankruptcy(self, ctx: commands.Context, percent: int):
        """Set the credit fine bankruptcy percentage on failure (0-100)."""
        if not (0 <= percent <= 100):
            return await ctx.send("⚠️ Percentage must be between 0 and 100.")
        await self.config.guild(ctx.guild).survivor_bankruptcy_percent.set(percent)
        await ctx.send(f"✅ Survivor failure bankruptcy penalty set to **{percent}%** of user's credits.")

    @survivor.command(name="setcontainment")
    async def surv_setcontainment(self, ctx: commands.Context, hours: int):
        """Set the containment/mute duration (in hours) on failure."""
        if hours < 0:
            return await ctx.send("⚠️ Duration cannot be negative.")
        await self.config.guild(ctx.guild).survivor_containment_hours.set(hours)
        await ctx.send(f"✅ Containment lockout duration set to **{hours} hours**.")

    @survivor.command(name="setexile")
    async def surv_setexile(self, ctx: commands.Context, hours: int):
        """Set the channel exile duration (in hours) on failure."""
        if hours < 0:
            return await ctx.send("⚠️ Exile duration cannot be negative.")
        await self.config.guild(ctx.guild).survivor_exile_hours.set(hours)
        await ctx.send(f"✅ Season exile ban duration set to **{hours} hours**.")

    @survivor.command(name="setfee")
    async def surv_setfee(self, ctx: commands.Context, credits: int):
        """Set the credit fee needed to buy a Survivor License."""
        if credits < 0:
            return await ctx.send("⚠️ Fee cannot be negative.")
        await self.config.guild(ctx.guild).survivor_license_fee.set(credits)
        await ctx.send(f"✅ Survivor License fee set to **{credits} credits**.")

    @survivor.command(name="setmincounts")
    async def surv_setmincounts(self, ctx: commands.Context, counts: int):
        """Set the highest progression counts required to type in Survivor channel."""
        if counts < 0:
            return await ctx.send("⚠️ Progression count cannot be negative.")
        await self.config.guild(ctx.guild).survivor_min_counts_req.set(counts)
        await ctx.send(f"✅ Minimum highest progression requirement set to **{counts}**.")

    @survivor.command(name="setrole")
    async def surv_setrole(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        """Set the shamed role given to failing players (containment role)."""
        guild = ctx.guild
        if not role:
            await self.config.guild(guild).containment_role_id.set(None)
            await ctx.send("✅ Containment role cleared. Monospace nick shaming will still be active.")
        else:
            await self.config.guild(guild).containment_role_id.set(role.id)
            await ctx.send(f"✅ Containment role set to {role.name}. Failing players will receive this role.")

    @survivor.command(name="config")
    async def surv_config(self, ctx: commands.Context):
        """View active Survivor configurations and jackpot status."""
        guild = ctx.guild
        enabled_ch = await self.config.guild(guild).survivor_channels()
        vault = await self.config.guild(guild).jackpot_vault()
        bank_pct = await self.config.guild(guild).survivor_bankruptcy_percent()
        cont_h = await self.config.guild(guild).survivor_containment_hours()
        exile_h = await self.config.guild(guild).survivor_exile_hours()
        min_p = await self.config.guild(guild).survivor_min_counts_req()
        fee = await self.config.guild(guild).survivor_license_fee()
        role_id = await self.config.guild(guild).containment_role_id()
        
        currency_name = "credits"
        try:
            currency_name = await bank.get_currency_name(guild)
        except Exception:
            pass
            
        role_mention = f"<@&{role_id}>" if role_id else "None (Nick Shame Only)"
        channels_mentions = [f"<#{cid}>" for cid in enabled_ch.keys()]
        ch_text = ", ".join(channels_mentions) if channels_mentions else "None"
        
        embed = discord.Embed(
            title="💀 Survivor Mode Configuration 💀",
            color=discord.Color.dark_purple()
        )
        embed.add_field(name="Survivor Channels", value=ch_text, inline=False)
        embed.add_field(name="Jackpot Vault Balance", value=f"💰 **{vault} {currency_name}**", inline=False)
        embed.add_field(name="Bankruptcy Deduction", value=f"{bank_pct}% of total balance", inline=True)
        embed.add_field(name="Containment Mute Time", value=f"{cont_h} hours", inline=True)
        embed.add_field(name="Season Exile Time", value=f"{exile_h} hours", inline=True)
        embed.add_field(name="License Fee", value=f"{fee} {currency_name}", inline=True)
        embed.add_field(name="Entry Progression Req", value=f"{min_p} counts", inline=True)
        embed.add_field(name="Containment Role", value=role_mention, inline=False)
        
        await ctx.send(embed=embed)

    # --- STARTUP OFFLINE RESYNC / CATCH-UP TASK ---
    async def catch_up_all_channels(self):
        await self.bot.wait_until_red_ready()
        
        for guild in self.bot.guilds:
            channels = await self.config.guild(guild).channels()
            survivor_channels = await self.config.guild(guild).survivor_channels()
            
            for ch_id_str, ch_data in list(channels.items()):
                channel = guild.get_channel(int(ch_id_str))
                if not channel:
                    continue
                    
                try:
                    # Read the last 100 messages
                    history = [msg async for msg in channel.history(limit=100, oldest_first=False)]
                except Exception:
                    continue
                    
                if not history:
                    continue
                    
                # Process from oldest to newest
                history.reverse()
                
                current_count = ch_data.get("current_count", 0)
                last_counter_id = ch_data.get("last_counter_id")
                is_survivor = ch_id_str in survivor_channels
                
                updated_count = current_count
                updated_last_counter = last_counter_id
                failed = False
                fail_msg = None
                fail_reason = None
                
                for msg in history:
                    if msg.author.bot:
                        continue
                        
                    words = msg.content.split()
                    if not words:
                        continue
                        
                    # Check if the first word is a number/math expression
                    parsed = evaluate_math(words[0])
                    if parsed is None:
                        # Non-number message (chatting in channel), completely ignore
                        continue

                    # Ignore numbers that are at or below current count (already processed before offline)
                    if parsed <= updated_count:
                        continue

                    if parsed == updated_count + 1:
                        # Next expected number!
                        if msg.author.id == updated_last_counter:
                            # Double count mistake
                            failed = True
                            fail_msg = msg
                            fail_reason = random.choice(self.DOUBLE_COUNT_REASONS)
                            break
                        # Update state
                        updated_count = parsed
                        updated_last_counter = msg.author.id
                        
                        # Add visual reactions retroactively
                        await self.safe_react(msg, "<:approved:1525751752987508737>", "✅")
                        if int(updated_count) % 100 == 0:
                            await self.safe_react(msg, "<a:text_gif_oof61:1515093296710422640>", "💯")
                        
                        # Update highest progression
                        member_highest = await self.config.member(msg.author).highest_progression()
                        if updated_count > member_highest:
                            await self.config.member(msg.author).highest_progression.set(int(updated_count))
                            
                        # If Survivor channel, track contribution
                        if is_survivor:
                            streak_id = ch_data.get("streak_id")
                            if streak_id:
                                user_streak_id = await self.config.member(msg.author).last_counted_streak_id()
                                if user_streak_id == streak_id:
                                    contrib = await self.config.member(msg.author).survivor_contributions()
                                    await self.config.member(msg.author).survivor_contributions.set(contrib + 1)
                                else:
                                    await self.config.member(msg.author).last_counted_streak_id.set(streak_id)
                                    await self.config.member(msg.author).survivor_contributions.set(1)
                                
                                contributors = ch_data.setdefault("contributors", [])
                                if msg.author.id not in contributors:
                                    contributors.append(msg.author.id)
                    else:
                        # Number skipped or wrong!
                        # Only trigger failure if the message was actually sent AFTER the current count was recorded
                        failed = True
                        fail_msg = msg
                        display_count = int(parsed) if parsed.is_integer() else parsed
                        template = random.choice(self.WRONG_NUMBER_TEMPLATES)
                        fail_reason = template.format(expected=int(updated_count + 1), got=display_count)
                        break
                        
                if failed:
                    async with self.config.guild(guild).channels() as active_channels:
                        # Reset streak in DB
                        ch_data["current_count"] = 0
                        ch_data["last_counter_id"] = None
                        if is_survivor:
                            ch_data["streak_id"] = str(random.randint(100000, 999999))
                            ch_data["contributors"] = []
                        active_channels[ch_id_str] = ch_data
                        
                    if is_survivor:
                        await self.apply_survivor_penalty(fail_msg.author, guild, int(updated_count), fail_reason, channel)
                    else:
                        await self.apply_penalty(fail_msg.author, guild)
                        
                        duration = await self.config.guild(guild).penalty_duration_hours()
                        penalty_name = await self.config.guild(guild).penalty_name()
                        template = random.choice(self.GAME_OVER_TEMPLATES)
                        description_text = template.format(
                            member=fail_msg.author.mention,
                            streak=int(updated_count),
                            channel=channel.mention,
                            reason=fail_reason,
                            penalty_name=penalty_name,
                            duration=duration
                        )
                        
                        embed = discord.Embed(
                            title="<:NoNo:1525751848362049676> RETROACTIVE GAME OVER! <:NoNo:1525751848362049676>",
                            description=f"An error occurred while the bot was offline:\n\n{description_text}",
                            color=discord.Color.red()
                        )
                        await channel.send(embed=embed)
                else:
                    if updated_count > current_count:
                        async with self.config.guild(guild).channels() as active_channels:
                            active_channels[ch_id_str]["current_count"] = int(updated_count)
                            active_channels[ch_id_str]["last_counter_id"] = updated_last_counter
                            if updated_count > active_channels[ch_id_str].get("high_score", 0):
                                active_channels[ch_id_str]["high_score"] = int(updated_count)
                        
                        diff = int(updated_count - current_count)
                        try:
                            await channel.send(
                                f"```ini\n"
                                f"[SYS] Matrix resynchronized. Caught up {diff} numbers.\n"
                                f"[SYS] Current Index: {int(updated_count)}\n"
                                f"```",
                                delete_after=600
                            )
                        except Exception:
                            pass
