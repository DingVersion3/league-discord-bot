# /openbet: a tracked player opens betting on their own next game.
# /bet: place a wager on someone's open bet.
# /honeyfruit: check your (or someone's) Honeyfruit balance.
import discord
import time
from discord import app_commands
from discord.ext import commands

from leaguebot.db import get_wallet, get_open_bet, get_leaderboard_channel, get_last_daily_claim, set_last_daily_claim, adjust_wallet
from . import betting

DAILY_BONUS = 100
SECONDS_PER_DAY = 24 * 60 * 60


class BettingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="openbet", description="Open betting on your own next game")
    async def openbet(self, interaction: discord.Interaction):
        channel_id = await get_leaderboard_channel(interaction.guild_id)
        if not channel_id:
            await interaction.response.send_message(
                "No leaderboard channel is set for this server yet — an admin needs to run "
                "`/setleaderboardchannel` before betting can be used.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message(
                "The configured leaderboard channel no longer exists — an admin needs to run "
                "`/setleaderboardchannel` again.",
                ephemeral=True,
            )
            return

        bet_id, error = await betting.open_bet(interaction.user.id, interaction.guild_id)

        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        await interaction.response.send_message(
            f"🎲 Betting on **{interaction.user.display_name}**'s next game has been posted to the leaderboard channel!",
            ephemeral=True,
        )

        await channel.send(
            f"🎲 Betting is open on **{interaction.user.display_name}**'s next game! "
            f"Use `/bet` to wager Honeyfruit on Win or Loss."
        )

    @app_commands.command(name="bet", description="Bet Honeyfruit on someone's open game")
    @app_commands.describe(
        player="The player whose open bet you're wagering on",
        prediction="Will they win or lose?",
        amount="How much Honeyfruit to wager",
    )
    @app_commands.choices(prediction=[
        app_commands.Choice(name="Win", value="win"),
        app_commands.Choice(name="Loss", value="loss"),
    ])
    async def bet(
        self,
        interaction: discord.Interaction,
        player: discord.Member,
        prediction: app_commands.Choice[str],
        amount: int,
    ):
        open_bet = await get_open_bet(player.id, interaction.guild_id)
        if not open_bet:
            await interaction.response.send_message(
                f"{player.display_name} doesn't have an open bet right now.", ephemeral=True
            )
            return

        error = await betting.place_bet(
            open_bet["bet_id"], interaction.user.id, player.id, interaction.guild_id, prediction.value, amount
        )

        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        await interaction.response.send_message(
            f"💰 {interaction.user.display_name} bet {amount} Honeyfruit on **{prediction.name}** for {player.display_name}."
        )

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


async def setup(bot: commands.Bot):
    await bot.add_cog(BettingCog(bot))