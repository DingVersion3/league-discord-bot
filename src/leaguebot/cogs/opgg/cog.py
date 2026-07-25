# /matchup: lane matchup guidance between two champions, via OP.GG.
# /tierlist: current lane tier list, via OP.GG.
import discord
from discord import app_commands
from discord.ext import commands

from leaguebot.opgg_client import get_lane_matchup, get_lane_tier_list, OpggError
from leaguebot.constants import POSITION_CHOICES, RIOT_TO_OPGG_POSITION


class OpggCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="matchup", description="Get lane matchup guidance between two champions")
    @app_commands.describe(
        my_champion="Your champion",
        opponent_champion="The enemy champion",
        position="Which lane this matchup is in",
    )
    @app_commands.choices(position=[app_commands.Choice(**c) for c in POSITION_CHOICES])
    async def matchup(
        self,
        interaction: discord.Interaction,
        my_champion: str,
        opponent_champion: str,
        position: app_commands.Choice[str],
    ):
        await interaction.response.defer()

        opgg_position = RIOT_TO_OPGG_POSITION[position.value]

        try:
            result = await get_lane_matchup(my_champion, opponent_champion, opgg_position)
        except OpggError as e:
            await interaction.followup.send(f"Couldn't get matchup data: {e.message}")
            return

        embed = discord.Embed(
            title=f"⚔️ {my_champion.title()} vs {opponent_champion.title()} — {position.name}",
            color=discord.Color.blue(),
        )
        if result["tip"]:
            embed.add_field(name="Tip", value=result["tip"], inline=False)
        if result["lane_advantage"]:
            embed.add_field(name="Lane Advantage", value=result["lane_advantage"], inline=True)
        if result["play_style"]:
            embed.add_field(name="Recommended Style", value=result["play_style"].title(), inline=True)
        if result["top_counters"]:
            embed.add_field(name="Top Counters", value=", ".join(result["top_counters"]), inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tierlist", description="Show the current lane tier list")
    @app_commands.describe(position="Which lane to show")
    @app_commands.choices(position=[app_commands.Choice(**c) for c in POSITION_CHOICES])
    async def tierlist(self, interaction: discord.Interaction, position: app_commands.Choice[str]):
        await interaction.response.defer()

        opgg_position = RIOT_TO_OPGG_POSITION[position.value]

        try:
            entries = await get_lane_tier_list(opgg_position)
        except OpggError as e:
            await interaction.followup.send(f"Couldn't get tier list: {e.message}")
            return

        TIER_LABELS = {0: "OP", 1: "S", 2: "A", 3: "B", 4: "C", 5: "D"}
        lines = [
            f"**{e['rank']}.** {e['champion']} — Tier {TIER_LABELS.get(e['tier'], e['tier'])} ({e['win_rate']*100:.0f}% WR)"
            for e in entries[:15]
        ]

        embed = discord.Embed(title=f"📊 Tier List — {position.name}", color=discord.Color.gold())
        embed.description = "\n".join(lines)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(OpggCog(bot))