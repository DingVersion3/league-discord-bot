# /matchup: lane matchup guidance between two champions, via OP.GG.
# /tierlist: current lane tier list, via cached OP.GG data (see fetch_opgg_tierlist.py).
import discord
from discord import app_commands
from discord.ext import commands

from leaguebot.constants import POSITION_CHOICES, RIOT_TO_OPGG_POSITION
from leaguebot.opgg_client import get_lane_matchup, get_lane_tier_list, OpggError

from leaguebot.cogs.leaderboard.board import get_server_champion_stats

BRACKET_CHOICES = [
    app_commands.Choice(name="Gold+", value="gold_plus"),
    app_commands.Choice(name="Diamond+", value="diamond_plus"),
    app_commands.Choice(name="All Ranks", value="all"),
]


class OpggCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="matchup", description="Get lane matchup guidance between two champions")
    @app_commands.describe(
        my_champion="Your champion",
        opponent_champion="The enemy champion",
        position="Which lane this matchup is in",
    )
    @app_commands.choices(
        position=[app_commands.Choice(**c) for c in POSITION_CHOICES],
    )
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
            result = await get_lane_matchup(
                my_champion, opponent_champion, opgg_position,
            )
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

        embed.add_field(name="\u200b", value="\u200b", inline=True)

        if result["weak_against"]:
            lines = [
                f"{c['champion']} — {c['win_rate']*100:.0f}% ({c['play']:,} games)"
                for c in result["weak_against"]
            ]
            embed.add_field(
                name=f"{my_champion.title()} Is Weak Against",
                value="\n".join(lines),
                inline=True,
            )

        if result["strong_against"]:
            lines = [
                f"{c['champion']} — {c['win_rate']*100:.0f}% ({c['play']:,} games)"
                for c in result["strong_against"]
            ]
            embed.add_field(
                name=f"{my_champion.title()} Is Strong Against",
                value="\n".join(lines),
                inline=True,
            )

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="tierlist", description="Show the current lane tier list")
    @app_commands.describe(
        position="Which lane to show",
        bracket="Rank bracket to show (default: Gold+)",
        include_off_meta="Also show off-meta picks (default: off)",
    )
    @app_commands.choices(
        position=[app_commands.Choice(**c) for c in POSITION_CHOICES],
        bracket=BRACKET_CHOICES,
    )
    async def tierlist(
        self,
        interaction: discord.Interaction,
        position: app_commands.Choice[str],
        bracket: app_commands.Choice[str] = None,
        include_off_meta: bool = False,
    ):
        await interaction.response.defer()

        opgg_position = RIOT_TO_OPGG_POSITION[position.value]
        bracket_value = bracket.value if bracket else "gold_plus"
        bracket_label = bracket.name if bracket else "Gold+"

        try:
            entries = get_lane_tier_list(opgg_position, bracket=bracket_value, include_off_meta=include_off_meta)
        except OpggError as e:
            await interaction.followup.send(f"Couldn't get tier list: {e.message}")
            return

        server_stats = await get_server_champion_stats(interaction.guild, position.value)

        TIER_LABELS = {0: "OP", 1: "S", 2: "A", 3: "B", 4: "C", 5: "D"}
        lines = []
        for e in entries[:25]:
            line = (
                f"{'⭐' if e['is_meta'] else '🔍'} **{e['rank']}.** {e['champion']} — "
                f"Tier {TIER_LABELS.get(e['tier'], e['tier'])} ({e['win_rate']*100:.0f}% WR, {e['pick_rate']*100:.0f}% PR)"
            )
            own = server_stats.get(e["champion"])
            if own and own["games"] > 0:
                win_pct = own["wins"] / own["games"] * 100
                line += f" · your server: {own['wins']}-{own['losses']} ({win_pct:.0f}%)"
            lines.append(line)

        embed = discord.Embed(title=f"📊 Tier List — {position.name} ({bracket_label})", color=discord.Color.gold())
        embed.description = "\n".join(lines)
        if include_off_meta:
            embed.set_footer(text="⭐ meta pick   🔍 off-meta pick")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(OpggCog(bot))