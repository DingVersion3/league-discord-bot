# /honeyfruit: check your (or someone's) Honeyfruit balance.
# /dailybonus: claim a daily Honeyfruit bonus.
# /mundododgeball: wager Honeyfruit head-to-head against another player.
import discord
import time
from discord import app_commands
from discord.ext import commands

from leaguebot.db import get_wallet, get_last_daily_claim, set_last_daily_claim, adjust_wallet
from leaguebot.constants import DAILY_BONUS, SECONDS_PER_DAY
from . import dodgeball


class BettingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="honeyfruit", description="Check your Honeyfruit balance")
    @app_commands.describe(user="Whose balance to check (defaults to you)")
    async def honeyfruit(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        balance = await get_wallet(target.id, interaction.guild_id)
        await interaction.response.send_message(f"🍯 {target.display_name} has **{balance}** Honeyfruit.")

    @app_commands.command(name="dailybonus", description="Claim your daily Honeyfruit bonus")
    async def dailybonus(self, interaction: discord.Interaction):
        last_claim = await get_last_daily_claim(interaction.user.id, interaction.guild_id)
        now = int(time.time())

        if now - last_claim < SECONDS_PER_DAY:
            remaining = SECONDS_PER_DAY - (now - last_claim)
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            await interaction.response.send_message(
                f"You already claimed today's bonus - you can find the Shopkeeper hanging out with ScuttleBuddy in {hours}hours and {minutes}minutes.",
                ephemeral=True,
            )
            return
        
        new_balance = await adjust_wallet(interaction.user.id, interaction.guild_id, DAILY_BONUS)
        await set_last_daily_claim(interaction.user.id, interaction.guild_id, now)
        await interaction.response.send_message(
            f"🍯 You claimed {DAILY_BONUS} Honeyfruit! New balance: {new_balance}."
        )

    @app_commands.command(name="mundododgeball", description="Challenge someone to Mundo Dodgeball for Honeyfruit")
    @app_commands.describe(opponent="Who you're challenging", amount="How much Honeyfruit to wager")
    async def mundododgeball(self, interaction: discord.Interaction, opponent: discord.Member, amount: int):
        if opponent.id == interaction.user.id:
            await interaction.response.send_message("You can't dodgeball yourself.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return

        can_play, seconds_remaining = await dodgeball.can_play(interaction.guild_id, interaction.user.id)
        if not can_play:
            hours = seconds_remaining // 3600
            minutes = (seconds_remaining % 3600) // 60
            await interaction.response.send_message(
                f"You've already played 3 dodgeball matches in the last 24 hours. "
                f"Try again in {hours}h {minutes}m.",
                ephemeral=True,
            )
            return

        balance = await get_wallet(interaction.user.id, interaction.guild_id)
        if balance < amount:
            await interaction.response.send_message(f"You only have {balance} Honeyfruit — can't wager {amount}.", ephemeral=True)
            return

        view = DodgeballChallengeView(interaction.user, opponent, amount, interaction.guild_id)
        await interaction.response.send_message(
            f"🥊 {opponent.mention}, {interaction.user.mention} has challenged you to **Mundo Dodgeball** for {amount} Honeyfruit! Accept?",
            view=view,
        )


class DodgeballChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, amount: int, guild_id: int):
        super().__init__(timeout=30)
        self.challenger = challenger
        self.opponent = opponent
        self.amount = amount
        self.guild_id = guild_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't yours to accept.", ephemeral=True)
            return

        opponent_balance = await get_wallet(self.opponent.id, self.guild_id)
        if opponent_balance < self.amount:
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(
                content=f"{self.opponent.mention} can't afford the {self.amount} Honeyfruit stake.", view=self
            )
            self.stop()
            return

        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="🩸 The dodgeball match begins!", view=self)
        self.stop()

        await adjust_wallet(self.challenger.id, self.guild_id, -self.amount)
        await adjust_wallet(self.opponent.id, self.guild_id, -self.amount)

        result = await dodgeball.play_match(
            self.guild_id, self.challenger.id, self.challenger.display_name,
            self.opponent.id, self.opponent.display_name,
        )

        pot = self.amount * 2
        if result["winner_id"] is None:
            await adjust_wallet(self.challenger.id, self.guild_id, self.amount)
            await adjust_wallet(self.opponent.id, self.guild_id, self.amount)
            outcome_line = "🤝 It's a tie! Stakes refunded."
        else:
            await adjust_wallet(result["winner_id"], self.guild_id, pot)
            winner_mention = self.challenger.mention if result["winner_id"] == self.challenger.id else self.opponent.mention
            outcome_line = f"🏆 {winner_mention} wins {pot} Honeyfruit!"

        narration = "\n".join(result["rounds"])
        await interaction.followup.send(f"{narration}\n\n{outcome_line}")

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("This challenge isn't yours to decline.", ephemeral=True)
            return
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(content="Challenge declined.", view=self)
        self.stop()

async def setup(bot: commands.Bot):
    await bot.add_cog(BettingCog(bot))