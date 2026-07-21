# /leaderboard: on-demand leaderboard, ranked by a chosen stat.
# /compare, /nemesis, /duo: player-vs-player and personal stat lookups.

import time

import discord
from discord import app_commands
from discord.ext import commands

from leaguebot.db import get_registered_user
from leaguebot.constants import SECONDS_PER_WEEK
from leaguebot.cogs.leaderboard.board import build_leaderboard_embed, build_compare_embed, get_nemesis, get_duo_stats

STAT_CHOICES = [
    app_commands.Choice(name="Win Rate", value="win_rate"),
    app_commands.Choice(name="Average KDA", value="kda"),
    app_commands.Choice(name="Total Wins", value="wins"),
    app_commands.Choice(name="Solo Queue Rank", value="rank"),
    app_commands.Choice(name="Double Kills", value="double_kills"),
    app_commands.Choice(name="Triple Kills", value="triple_kills"),
    app_commands.Choice(name="Quadra Kills", value="quadra_kills"),
    app_commands.Choice(name="Penta Kills", value="penta_kills"),
    app_commands.Choice(name="Honeyfruit", value="honeyfruit"),
]


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show the server leaderboard")
    @app_commands.describe(stat="Which stat to rank by")
    @app_commands.choices(stat=STAT_CHOICES)
    async def leaderboard(self, interaction: discord.Interaction, stat: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await build_leaderboard_embed(interaction.guild, stat.value)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="compare", description="Compare two players' stats for the week")
    @app_commands.describe(user1="First player", user2="Second player")
    async def compare(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        await interaction.response.defer()
        embed = await build_compare_embed(interaction.guild, user1, user2)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="nemesis", description="See which enemy champion beats you most")
    @app_commands.describe(user="Whose nemesis to check (defaults to you)")
    async def nemesis(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer()
        target = user or interaction.user

        since = int(time.time()) - SECONDS_PER_WEEK
        nemesis = await get_nemesis(target.id, since)

        if not nemesis:
            await interaction.followup.send(f"{target.display_name} has no losses this week — no nemesis found. 🎉 Did you play at all this week? 😡")
            return

        await interaction.followup.send(
            f"{target.display_name}'s nemesis this week: **{nemesis['champion']}** "
            f"({nemesis['losses']} loss{'es' if nemesis['losses'] != 1 else ''})"
        )

    @app_commands.command(name="duo", description="See win rate and stats when two players queue together")
    @app_commands.describe(user1="First player", user2="Second player")
    async def duo(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        await interaction.response.defer()

        record_a = await get_registered_user(user1.id)
        record_b = await get_registered_user(user2.id)

        if not record_a or not record_b:
            missing = user1.display_name if not record_a else user2.display_name
            await interaction.followup.send(f"{missing} hasn't registered yet — use `/register` first.")
            return

        stats = await get_duo_stats(user1.id, user2.id)

        if not stats:
            await interaction.followup.send(
                f"{user1.display_name} and {user2.display_name} haven't played together this week."
            )
            return

        embed = discord.Embed(
            title=f"🤝 Duo Synergy — {user1.display_name} & {user2.display_name}",
            color=discord.Color.green(),
        )
        embed.add_field(name="Games Together", value=str(stats["games"]), inline=True)
        embed.add_field(name="Wins", value=str(stats["wins"]), inline=True)
        embed.add_field(name="Win Rate", value=f"{stats['win_rate']*100:.0f}%", inline=True)
        embed.add_field(name=f"{user1.display_name}'s KDA", value=f"{stats['avg_kda_a']:.2f}", inline=True)
        embed.add_field(name=f"{user2.display_name}'s KDA", value=f"{stats['avg_kda_b']:.2f}", inline=True)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))