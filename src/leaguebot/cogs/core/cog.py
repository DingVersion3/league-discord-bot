# /help: lists every available command, grouped by category.
import discord
from discord import app_commands
from discord.ext import commands

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


async def setup(bot: commands.Bot):
    await bot.add_cog(CoreCog(bot))