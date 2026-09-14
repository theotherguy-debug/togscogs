import discord
from redbot.core import commands
from redbot.core import Config, bank
from discord import ui

# --- ANSI Terminal Colors ---
RED = "\u001b[1;31m"
GREEN = "\u001b[1;32m"
YELLOW = "\u001b[1;33m"
CYAN = "\u001b[1;36m"
WHITE = "\u001b[1;37m"
RESET = "\u001b[0m"

class ATM(commands.Cog):
    """Cyberpunk-themed interactive ATM interface for personal economy management."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=93475893475, force_registration=True)
        self.config.register_user(last_mine_time=0.0)
        self.config.register_global(mining_reward=1000, mining_cooldown=86400)


    @commands.hybrid_command(name="atm", aliases=["bank", "netatm"])
    @commands.guild_only()
    async def atm(self, ctx: commands.Context):
        """Open the unified ATM terminal mainframe panel."""
        view = ATMView(self.bot, ctx.author)
        embed = await view.get_main_embed(ctx.guild)
        message = await ctx.send(embed=embed, view=view)
        view.message = message


class ATMView(ui.View):
    def __init__(self, bot, author):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ You are not authorized to use this ATM terminal.", ephemeral=True)
            return False
        return True

    async def get_main_embed(self, guild: discord.Guild) -> discord.Embed:
        # Fetch basic economy info
        is_global = await bank.is_global()
        currency_name = await bank.get_currency_name(guild)
        
        balance = await bank.get_balance(self.author)

        desc = (
            f"```ansi\n"
            f"{CYAN}╔══════════════════════════════════════════════════════╗{RESET}\n"
            f"{CYAN}║             NETWORK ATM TERMINAL ONLINE              ║{RESET}\n"
            f"{CYAN}╚══════════════════════════════════════════════════════╝{RESET}\n\n"
            f" [STATUS]: {GREEN}🟢 SECURE CONNECTION ESTABLISHED{RESET}\n"
            f" [USER]:   {WHITE}{self.author.name}#{self.author.discriminator}{RESET}\n"
            f" [FUNDS]:  {YELLOW}{balance:,} {currency_name}{RESET}\n\n"
            f" Select an operation below to proceed with transaction.\n"
            f"```"
        )
        embed = discord.Embed(title="💳 ATM Access Terminal", description=desc, color=discord.Color.dark_teal())
        embed.set_footer(text="Decryption Division • Financial Mainframe")
        embed.set_thumbnail(url=self.author.display_avatar.url)
        return embed

    @ui.button(label="Refresh Balance", style=discord.ButtonStyle.primary, emoji="🔄", row=0)
    async def refresh_btn(self, interaction: discord.Interaction, button: ui.Button):
        embed = await self.get_main_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="Transfer Funds", style=discord.ButtonStyle.success, emoji="💸", row=0)
    async def transfer_btn(self, interaction: discord.Interaction, button: ui.Button):
        modal = ATMTransferModal(self.bot)
        await interaction.response.send_modal(modal)

    @ui.button(label="Mine Crypto", style=discord.ButtonStyle.primary, emoji="⛏️", row=0)
    async def mine_btn(self, interaction: discord.Interaction, button: ui.Button):
        import time
        atm_cog = self.bot.get_cog("ATM")
        if not atm_cog:
            return await interaction.response.send_message("❌ ATM system error.", ephemeral=True)
            
        last_mine = await atm_cog.config.user(self.author).last_mine_time()
        cooldown = await atm_cog.config.mining_cooldown()
        reward = await atm_cog.config.mining_reward()
        now = time.time()
        
        if now - last_mine < cooldown:
            rem = int(cooldown - (now - last_mine))
            h = rem // 3600
            m = (rem % 3600) // 60
            return await interaction.response.send_message(f"⏳ Mining rigs are cooling down. Try again in **{h}h {m}m**.", ephemeral=True)
            
        await atm_cog.config.user(self.author).last_mine_time.set(now)
        try:
            await bank.deposit_credits(self.author, reward)
            currency = await bank.get_currency_name(interaction.guild)
            await interaction.response.send_message(f"✅ **MINING COMPLETE:** You extracted **{reward} {currency}** from the blockchain!", ephemeral=True)
            # Update embed
            embed = await self.get_main_embed(interaction.guild)
            await interaction.message.edit(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Transaction Failed: {str(e)}", ephemeral=True)

    @ui.button(label="Wealth Leaderboard", style=discord.ButtonStyle.secondary, emoji="🏆", row=1)
    async def leaderboard_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        is_global = await bank.is_global()
        if is_global:
            accounts = await bank.get_all_accounts()
        else:
            accounts = await bank.get_all_accounts(interaction.guild)
            
        sorted_accounts = sorted(accounts, key=lambda x: x.balance, reverse=True)
        currency_name = await bank.get_currency_name(interaction.guild)
        
        leaderboard_lines = []
        count = 0
        for acc in sorted_accounts:
            member = interaction.guild.get_member(acc.member_id) if not is_global else self.bot.get_user(acc.member_id)
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
                rank_color = "\u001b[1;30m" # Dark Gray
                
            name_padded = (member.display_name[:18] + "..") if len(member.display_name) > 18 else member.display_name
            name_col = f"{name_padded:<20}"
            
            leaderboard_lines.append(
                f"  {rank_color}{rank_str}{RESET}  {WHITE}{name_col}{RESET}  {GREEN}{acc.balance:,} {currency_name}{RESET}"
            )
            
            if count >= 10:
                break
                
        if not leaderboard_lines:
            leaderboard_lines.append("  No accounts registered in database.")
            
        desc = (
            f"```ansi\n"
            f"{CYAN}╔══════════════════════════════════════════════════════╗{RESET}\n"
            f"{CYAN}║            TOP ACCOUNTS WEALTH LEADERBOARD           ║{RESET}\n"
            f"{CYAN}╚══════════════════════════════════════════════════════╝{RESET}\n\n"
            f"  Rank  Operative             Balance\n"
            + "\n".join(leaderboard_lines) +
            f"\n```"
        )
        embed = discord.Embed(
            title="🏆 Wealth Leaderboard",
            description=desc,
            color=discord.Color.gold()
        )
        embed.set_footer(text="Data compiled from financial mainframe")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ui.button(label="App Store", style=discord.ButtonStyle.primary, emoji="🛒", row=1)
    async def store_btn(self, interaction: discord.Interaction, button: ui.Button):
        netcount_cog = self.bot.get_cog("NetCount")
        if not netcount_cog:
            return await interaction.response.send_message("❌ Subsystem offline. NetCount integration is currently unavailable.", ephemeral=True)
            
        store_view = ATMStoreView(self.bot, self.author, self, netcount_cog)
        embed = await store_view.get_embed(interaction.guild, interaction.channel)
        await interaction.response.edit_message(embed=embed, view=store_view)

    @ui.button(label="Terminate Session", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def exit_btn(self, interaction: discord.Interaction, button: ui.Button):
        for item in self.children:
            item.disabled = True
        desc = "```ansi\n [LOG]: Connection to ATM Terminal safely terminated.\n```"
        embed = discord.Embed(title="❌ Terminated Connection", description=desc, color=discord.Color.dark_red())
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()

class ATMStoreView(ui.View):
    def __init__(self, bot, author, parent_view, netcount_cog):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.parent_view = parent_view
        self.netcount_cog = netcount_cog

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ You are not authorized to use this ATM terminal.", ephemeral=True)
            return False
        return True

    async def get_embed(self, guild, channel):
        balance = await bank.get_balance(self.author)
        currency_name = await bank.get_currency_name(guild)
        
        has_lic = await self.netcount_cog.config.member(self.author).has_survivor_license()
        surv_fee = await self.netcount_cog.config.guild(guild).survivor_license_fee()
        
        ch_str = str(channel.id)
        channels = await self.netcount_cog.config.guild(guild).channels()
        ch_data = channels.get(ch_str)
        
        save_status = "Available for current channel" if ch_data else "Unavailable here (Not a counting channel)"
        save_price = ch_data.get("save_price", 5000) if ch_data else "N/A"
        
        desc = (
            f"```ansi\n"
            f"{CYAN}╔══════════════════════════════════════════════════════╗{RESET}\n"
            f"{CYAN}║                 MAINFRAME APP STORE                  ║{RESET}\n"
            f"{CYAN}╚══════════════════════════════════════════════════════╝{RESET}\n\n"
            f" [FUNDS]: {YELLOW}{balance:,} {currency_name}{RESET}\n\n"
            f" 🛡️ **Network Save Token**\n"
            f"  Status: {GREEN if ch_data else RED}{save_status}{RESET}\n"
            f"  Cost:   {WHITE}{save_price} {currency_name}{RESET}\n\n"
            f" 🎫 **Lifetime Survivor License**\n"
            f"  Status: {GREEN if has_lic else YELLOW}{'Owned' if has_lic else 'Not Owned'}{RESET}\n"
            f"  Cost:   {WHITE}{surv_fee:,} {currency_name}{RESET}\n"
            f"```"
        )
        return discord.Embed(title="🛒 ATM Software Store", description=desc, color=discord.Color.purple())

    @ui.button(label="Buy Save Token", style=discord.ButtonStyle.success, emoji="🛡️", row=0)
    async def buy_save_btn(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        channel = interaction.channel
        ch_str = str(channel.id)
        
        channels = await self.netcount_cog.config.guild(guild).channels()
        if ch_str not in channels:
            return await interaction.response.send_message("❌ This channel is not an active NetCount channel.", ephemeral=True)
            
        ch_data = channels[ch_str]
        use_eco = ch_data.get("use_economy", False)
        if not use_eco:
            return await interaction.response.send_message("❌ Economy integration is offline in this channel.", ephemeral=True)
            
        price = ch_data.get("save_price", 5000)
        
        try:
            can_spend = await bank.can_spend(self.author, price)
            if not can_spend:
                currency_name = await bank.get_currency_name(guild)
                return await interaction.response.send_message(f"❌ Insufficient funds. You need **{price} {currency_name}**.", ephemeral=True)
                
            await bank.withdraw_credits(self.author, price)
            
            async with self.netcount_cog.config.guild(guild).channels() as active_channels:
                active_channels[ch_str]["saves"] = active_channels[ch_str].get("saves", 0) + 1
                new_saves = active_channels[ch_str]["saves"]
                
            await interaction.response.send_message(f"✅ **PURCHASE COMPLETE:** Added 1 Save Token to <#{channel.id}>. Total saves here: **{new_saves}**.", ephemeral=True)
            
            # Refresh view
            embed = await self.get_embed(guild, channel)
            await interaction.message.edit(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Transaction Failed: {str(e)}", ephemeral=True)

    @ui.button(label="Buy Survivor License", style=discord.ButtonStyle.success, emoji="🎫", row=0)
    async def buy_surv_btn(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        
        has_lic = await self.netcount_cog.config.member(self.author).has_survivor_license()
        if has_lic:
            return await interaction.response.send_message("❌ You already own a Survivor License.", ephemeral=True)
            
        fee = await self.netcount_cog.config.guild(guild).survivor_license_fee()
        if fee <= 0:
            return await interaction.response.send_message("❌ Survivor Licenses are currently free or disabled on this server.", ephemeral=True)
            
        try:
            can_spend = await bank.can_spend(self.author, fee)
            if not can_spend:
                currency_name = await bank.get_currency_name(guild)
                return await interaction.response.send_message(f"❌ Insufficient funds. You need **{fee:,} {currency_name}**.", ephemeral=True)
                
            await bank.withdraw_credits(self.author, fee)
            await self.netcount_cog.config.member(self.author).has_survivor_license.set(True)
            
            await interaction.response.send_message(f"✅ **PURCHASE COMPLETE:** Lifetime Survivor License acquired!", ephemeral=True)
            
            # Refresh view
            embed = await self.get_embed(guild, interaction.channel)
            await interaction.message.edit(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Transaction Failed: {str(e)}", ephemeral=True)

    @ui.button(label="Back to ATM", style=discord.ButtonStyle.danger, emoji="⬅️", row=1)
    async def back_btn(self, interaction: discord.Interaction, button: ui.Button):
        embed = await self.parent_view.get_main_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self.parent_view)



class ATMTransferModal(ui.Modal, title="Wire Transfer Funds"):
    recipient = ui.TextInput(label="Recipient (User ID or Name)", placeholder="E.g. 1234567890 or username")
    amount = ui.TextInput(label="Amount to Transfer", placeholder="E.g. 1000")

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        sender = interaction.user
        
        # 1. Resolve Recipient
        target_str = str(self.recipient).strip()
        target = None
        if target_str.isdigit():
            target = guild.get_member(int(target_str))
        else:
            target = discord.utils.find(lambda m: m.name == target_str or m.display_name == target_str, guild.members)
            
        if not target:
            return await interaction.followup.send("❌ Transaction Failed: Recipient not found in network.", ephemeral=True)
            
        if target.id == sender.id:
            return await interaction.followup.send("❌ Transaction Failed: Cannot wire funds to yourself.", ephemeral=True)
            
        if target.bot:
            return await interaction.followup.send("❌ Transaction Failed: Automated agents cannot hold accounts.", ephemeral=True)

        # 2. Resolve Amount
        try:
            amt = int(str(self.amount).strip())
            if amt <= 0:
                raise ValueError
        except ValueError:
            return await interaction.followup.send("❌ Transaction Failed: Invalid amount. Must be a positive integer.", ephemeral=True)

        # 3. Check Balance and Transfer
        try:
            can_spend = await bank.can_spend(sender, amt)
            if not can_spend:
                currency_name = await bank.get_currency_name(guild)
                return await interaction.followup.send(f"❌ Transaction Failed: Insufficient funds. You do not have **{amt:,} {currency_name}**.", ephemeral=True)
                
            await bank.transfer_credits(sender, target, amt)
            currency_name = await bank.get_currency_name(guild)
            
            # Send success receipt
            receipt_desc = (
                f"```ansi\n"
                f"{GREEN}╔══════════════════════════════════════════════════════╗{RESET}\n"
                f"{GREEN}║               WIRE TRANSFER RECEIPT                  ║{RESET}\n"
                f"{GREEN}╚══════════════════════════════════════════════════════╝{RESET}\n\n"
                f" [STATUS]: {GREEN}🟢 TRANSACTION SUCCESSFUL{RESET}\n"
                f" [SENDER]: {WHITE}{sender.display_name}{RESET}\n"
                f" [TARGET]: {WHITE}{target.display_name}{RESET}\n"
                f" [AMOUNT]: {YELLOW}{amt:,} {currency_name}{RESET}\n"
                f"```"
            )
            embed = discord.Embed(title="🧾 Transfer Receipt", description=receipt_desc, color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Optionally notify the recipient
            try:
                notify_desc = (
                    f"```ansi\n"
                    f"{GREEN}╔══════════════════════════════════════════════════════╗{RESET}\n"
                    f"{GREEN}║               INCOMING WIRE TRANSFER                 ║{RESET}\n"
                    f"{GREEN}╚══════════════════════════════════════════════════════╝{RESET}\n\n"
                    f" You received {YELLOW}{amt:,} {currency_name}{RESET} from {WHITE}{sender.display_name}{RESET}.\n"
                    f"```"
                )
                notify_embed = discord.Embed(title="💸 Funds Received", description=notify_desc, color=discord.Color.green())
                await target.send(embed=notify_embed)
            except discord.Forbidden:
                pass # DMs closed
                
        except bank.errors.BalanceTooHigh as e:
            await interaction.followup.send(f"❌ Transaction Failed: Recipient's bank balance would exceed the maximum limit ({e.max_balance:,}).", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Transaction Failed: Critical system error ({str(e)}).", ephemeral=True)
