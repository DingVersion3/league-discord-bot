# /help: lists every available command, grouped by category.
import discord
from discord import app_commands
from discord.ext import commands

from leaguebot.db import get_registered_user, get_rank, get_streak, get_wallet
from leaguebot.cogs.leaderboard.board import _weekly_stats_for_user

CATEGORY_ORDER = [
    "Track & Compare",
    "Live Alerts",
    "Honeyfruit Betting",
    "Fun",
    "Admin",
]

COMMAND_CATEGORIES = {
    "register": "Track & Compare",
    "lastgame": "Track & Compare",
    "leaderboard": "Track & Compare",
    "compare": "Track & Compare",
    "nemesis": "Track & Compare",
    "duo": "Track & Compare",
    "whoshouldiplay": "Track & Compare",
    "profile": "Track & Compare",
    "streak": "Live Alerts",
    "openbet": "Honeyfruit Betting",
    "bet": "Honeyfruit Betting",
    "honeyfruit": "Honeyfruit Betting",
    "dailybonus": "Honeyfruit Betting",
    "randomchamp": "Fun",
    "memestats": "Fun",
    "teamcomp": "Fun",
    "setleaderboardchannel": "Admin",
    "syncnow": "Admin",
}


class CoreCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="List all ScuttleBuddy commands")
    async def help(self, interaction: discord.Interaction):
        all_commands = self.bot.tree.walk_commands()

        grouped = {category: [] for category in CATEGORY_ORDER}
        for command in all_commands:
            if isinstance(command, app_commands.Group):
                continue
            category = COMMAND_CATEGORIES.get(command.name, "Fun")
            description = command.description or "No description."
            grouped[category].append(f"`/{command.name}` — {description}")

        embed = discord.Embed(title="🦀 ScuttleBuddy Commands", color=discord.Color.blue())
        for category in CATEGORY_ORDER:
            entries = grouped[category]
            if entries:
                embed.add_field(name=category, value="\n".join(entries), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="profile", description="Your Scuttlebuddy profile: rank, streak, weekly stats and Honeyfruit")
    @app_commands.describe(user="Whose profile to check(defaults to you)")
    async def profile(self, interaction: discord.Interaction, user: discord.Member | None = None):
        await interaction.response.defer()
        target = user or interaction.user

        record = await get_registered_user(target.id)
        if not record:
            await interaction.followup.send(
                f"{target.mention} hasn't registered yet - use `/register` first."
            )
            return
        
        rank = await get_rank(target.id)
        streak = await get_streak(target.id)
        weekly = await _weekly_stats_for_user(target.id)
        balance = await get_wallet(target.id, interaction.guild_id)

        embed = discord.Embed(
            title=f"{target.display_name}'s Profile",
            description=f"{record['game_name']}#{record['tag_line']}",
            color=discord.Color.blue(),
        )

        if rank and rank["tier"]:
            rank_text = f"{rank['tier'].title()} {rank['rank']} ({rank['league_points']} LP)"
        else:
            rank_text = "Unranked"
        embed.add_field(name="Rank", value=rank_text, inline=True)

        if streak and streak["streak_type"] != "none":
            emoji = "🔥" if streak["streak_type"] == "win" else "💀"
            streak_text = f"{emoji} {streak['current_streak']}-game {streak['streak_type']} streak"
        else:
            streak_text = "No active streak"
        embed.add_field(name="Streak", value=streak_text, inline=True)

        embed.add_field(name="Honeyfruit", value=f"🍯 {balance:,}", inline=True)

        if weekly:
            weekly_text = (
                f"{weekly['games']} games - {weekly['win_rate']*100:.0f}% win rate\n"
                f"{weekly['avg_kda']:.2f} average KDA"
            )
        else:
            weekly_text = "No games played this week 😡"
        embed.add_field(name="This Week", value=weekly_text, inline=False)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(CoreCog(bot))