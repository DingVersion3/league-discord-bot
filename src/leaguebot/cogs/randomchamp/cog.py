# The /randomchamp slash command: picks a random champion and a random legal rune page, and posts them as an embed.
# The /teamcomp slash command: generates a random position/champion assignment for a group of players.
import json
import random
import re
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from leaguebot.cogs.randomchamp.runes import build_random_page

DATA_DIR = Path(__file__).parents[4] / "data"

POSITIONS = ["Top", "Jungle", "Mid", "ADC", "Support"]


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

    @app_commands.command(name="teamcomp", description="Generate a random team comp for your lobby")
    @app_commands.describe(
        players="Mention everyone playing, e.g. @user1 @user2 @user3 @user4",
        team_a="Optional: mention who's on Team A, e.g. @user1 @user2 (leave blank to auto-assign teams)",
        team_b="Optional: mention who's on Team B (only used if team_a is also set)",
        randomize_runes="Also assign a random keystone rune to each player",
    )
    async def teamcomp(
        self,
        interaction: discord.Interaction,
        players: str | None = None,
        team_a: str | None = None,
        team_b: str | None = None,
        randomize_runes: bool = False,
    ):
        def parse_mentions(text: str | None) -> list[discord.Member]:
            if not text:
                return []
            ids = [int(uid) for uid in re.findall(r"<@!?(\d+)>", text)]
            members = [interaction.guild.get_member(uid) for uid in ids]
            return [m for m in members if m is not None]

        if team_a or team_b:
            list_a = parse_mentions(team_a)
            list_b = parse_mentions(team_b)
            if not list_a or not list_b:
                await interaction.response.send_message(
                    "If setting teams manually, mention at least one player on each side.",
                    ephemeral=True,
                )
                return
        else:
            everyone = parse_mentions(players)
            if len(everyone) < 2:
                await interaction.response.send_message(
                    "Mention at least 2 players (via `players`, or split into `team_a`/`team_b`).",
                    ephemeral=True,
                )
                return
            random.shuffle(everyone)
            midpoint = len(everyone) // 2
            list_a, list_b = everyone[:midpoint], everyone[midpoint:]

        is_full_5v5 = len(list_a) == 5 and len(list_b) == 5
        positions_a = random.sample(POSITIONS, len(list_a)) if is_full_5v5 else [None] * len(list_a)
        positions_b = random.sample(POSITIONS, len(list_b)) if is_full_5v5 else [None] * len(list_b)

        champs_needed = len(list_a) + len(list_b)
        champion_pool = random.sample(list(self.champions.items()), champs_needed)
        champs_a = champion_pool[:len(list_a)]
        champs_b = champion_pool[len(list_a):]

        def format_side(members, positions, champs):
            lines = []
            for member, position, (champion_id, champion_name) in zip(members, positions, champs):
                rune_suffix = ""
                if randomize_runes:
                    page = build_random_page()
                    rune_suffix = f" — {page['keystone']}"
                label = f"{position}: " if position else ""
                lines.append(f"{label}**{member.display_name}** ({champion_name}){rune_suffix}")
            return "\n".join(lines)

        embed = discord.Embed(title="🎲 Random Team Comp", color=discord.Color.blue())
        embed.add_field(name="Team A", value=format_side(list_a, positions_a, champs_a), inline=True)
        embed.add_field(name="Team B", value=format_side(list_b, positions_b, champs_b), inline=True)

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(RandomChampCog(bot))