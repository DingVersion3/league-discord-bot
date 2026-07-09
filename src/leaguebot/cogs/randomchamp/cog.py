# The /randomchamp slash command: picks a random champion and a random legal rune page, and posts them as an embed.
import json
import random
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from leaguebot.cogs.randomchamp.runes import build_random_page

DATA_DIR = Path(__file__).parents[4] / "data"


def load_champions() -> dict[str, str]:
    with open(DATA_DIR / "champions.json") as f:
        return json.load(f)["champions"]


class RandomChampCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.champions = load_champions()

    @app_commands.command(name="randomchamp", description="Get a random champion and rune page")
    async def randomchamp(self, interaction: discord.Interaction):
        champion_id, champion_name = random.choice(list(self.champions.items()))
        page = build_random_page()

        embed = discord.Embed(
            title=f"🎲 {champion_name}",
            color=discord.Color.blue(),
        )
        embed.set_image(url=f"https://ddragon.leagueoflegends.com/cdn/img/champion/splash/{champion_id}_0.jpg")
        embed.add_field(
            name=f"Primary: {page['primary_tree']}",
            value=f"**{page['keystone']}**\n" + "\n".join(page["primary_runes"]),
            inline=True,
        )
        embed.add_field(
            name=f"Secondary: {page['secondary_tree']}",
            value="\n".join(page["secondary_runes"]),
            inline=True,
        )
        embed.add_field(
            name="Shards",
            value="\n".join(f"{k}: {v}" for k, v in page["shards"].items()),
            inline=False,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RandomChampCog(bot))