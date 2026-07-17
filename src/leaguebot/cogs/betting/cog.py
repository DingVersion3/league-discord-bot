# /openbet: a tracked player opens betting on their own next game.
# /bet: place a wager on someone's open bet.
# /honeyfruit: check your (or someone's) Honeyfruit balance.
import discord
from discord import app_commands
from discord.ext import commands

from leaguebot.db import get_wallet, get_open_bet, get_leaderboard_channel
from . import betting


class BettingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="openbet", description="Open betting on your own next game")
    async def openbet(self, interaction: discord.Interaction):
        bet_id, error = await betting.open_bet(interaction.user.id)

        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        await interaction.response.send_message(
            f"🎲 Betting is open on **{interaction.user.display_name}**'s next game! "
            f"Use `/bet` to wager Honeyfruit on Win or Loss."
        )

        # Also post to the leaderboard channel(s) so people not watching this channel see it
        for guild in self.bot.guilds:
            if guild.get_member(interaction.user.id) is None:
                continue
            channel_id = await get_leaderboard_channel(guild.id)
            if not channel_id:
                continue
            channel = guild.get_channel(channel_id)
            if channel and channel.id != interaction.channel_id:
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
        open_bet = await get_open_bet(player.id)
        if not open_bet:
            await interaction.response.send_message(
                f"{player.display_name} doesn't have an open bet right now.", ephemeral=True
            )
            return

        error = await betting.place_bet(
            open_bet["bet_id"], interaction.user.id, player.id, prediction.value, amount
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
        balance = await get_wallet(target.id)
        await interaction.response.send_message(f"🍯 {target.display_name} has **{balance}** Honeyfruit.")


async def setup(bot: commands.Bot):
    await bot.add_cog(BettingCog(bot))