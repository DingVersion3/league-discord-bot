# /worldspicks: enter the Worlds Finals Pick'em for 1000 Honeyfruit, or view your picks if you've already entered.
# Entries close automatically at voting.LOCK_TIME (Nov 14, 10:59 AM PT).
# /worldsresults: owner only - enter the real answers and pay everyone out immediately.
import json
import time

import discord
from discord import app_commands
from discord.ext import commands

from leaguebot.db import (
    adjust_wallet, get_leaderboard_channel, get_unpaid_worlds_picks,
    get_wallet, get_worlds_pick, get_worlds_picks_for_guild, save_worlds_pick,
    set_bot_state, set_worlds_payout,
)
from leaguebot.helpers import log
from . import voting

RESULTS_KEY = "worlds:results"

PLAYER_OPTIONS = [(voting.player_label(p), p) for p in voting.PLAYERS]
SERIES_OPTIONS = [(o, o) for o in voting.SERIES_OPTIONS]
TEAM_OPTIONS = [(t, t) for t in voting.TEAMS]
YES_NO_OPTIONS = [("Yes", "Yes"), ("No", "No")]
OVER_UNDER_OPTIONS = [
    (f"Over {voting.DURATION_LINE_MINUTES} minutes", "Over"),
    (f"Under {voting.DURATION_LINE_MINUTES} minutes", "Under"),
]
PENTA_OPTIONS = [("No Pentakill", voting.NO_PENTA)] + PLAYER_OPTIONS
PAGES = [
    [
        ("series", "1. Who wins, and what's the series score?", SERIES_OPTIONS),
        ("highest_kda", "2. Highest average KDA", PLAYER_OPTIONS),
        ("worst_kda", "3. Worst average KDA", PLAYER_OPTIONS),
        ("most_kills_player", "4. Most kills in a single game", PLAYER_OPTIONS),
    ],
    [
        ("most_scuttles", "5. Most Scuttle Crabs in the series", PLAYER_OPTIONS),
        ("nidalee", "6. Will Nidalee be played?", YES_NO_OPTIONS),
        ("first_baron", "9. First Baron of the series", TEAM_OPTIONS),
        ("duration_ou", f"10. Total series time: Over/Under {voting.DURATION_LINE_MINUTES} min", OVER_UNDER_OPTIONS),
    ],
    [
        ("penta_player", "7. BONUS: Who gets a Pentakill?", PENTA_OPTIONS),
    ],
]

def picks_embed(member: discord.abc.User, row: dict) -> discord.Embed:
    picks = json.loads(row["picks"])
    embed = discord.Embed(
        title=f"🏆 {member.display_name}'s Worlds Pick'em",
        description="\n".join(voting.describe_picks(picks)),
        color=discord.Color.gold(),
    )
    if row.get("payout") is not None:
        embed.add_field(
            name="Result",
            value=f"{row['correct']}/{len(voting.SCORED_ITEMS)} correct · won **{row['payout']}** Honeyfruit",
        )
    return embed

async def player_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    parts = current.split(",")
    prefix = ", ".join(p.strip() for p in parts[:-1] if p.strip())
    last = parts[-1].strip().lower()
    choices = []
    for player in voting.PLAYERS:
        if player.lower().startswith(last):
            value = f"{prefix}, {player}" if prefix else player
            choices.append(app_commands.Choice(name=value, value=value))
    return choices[:25]


class NumbersModal(discord.ui.Modal, title="Worlds Pick'em - the numbers"):
    most_kills_count = discord.ui.TextInput(label="4. How many kills will that player get?", placeholder="e.g. 11", max_length=3)
    pentakills = discord.ui.TextInput(label="7. How many Pentakills in the series?", placeholder="0 if none", max_length=2)
    unique_champs = discord.ui.TextInput(label="8. Unique champs picked + banned", placeholder="e.g. 62", max_length=3)
    duration = discord.ui.TextInput(label="10. BONUS: Exact total series time (mm:ss)", placeholder="e.g. 148:32", max_length=7)

    def __init__(self, picks_view: "PicksView"):
        super().__init__()
        self.picks_view = picks_view
        saved = picks_view.numbers
        self.most_kills_count.default = saved.get("most_kills_count")
        self.pentakills.default = saved.get("pentakills")
        self.unique_champs.default = saved.get("unique_champs")
        self.duration.default = saved.get("duration")

    async def on_submit(self, interaction: discord.Interaction):
        self.picks_view.numbers = {
            "most_kills_count": self.most_kills_count.value,
            "pentakills": self.pentakills.value,
            "unique_champs": self.unique_champs.value,
            "duration": self.duration.value,
        }

        picks = dict(self.picks_view.picks)
        try:
            picks["most_kills_count"] = int(self.most_kills_count.value)
            picks["pentakills"] = int(self.pentakills.value)
            picks["unique_champs"] = int(self.unique_champs.value)
        except ValueError:
            await interaction.response.send_message("Kills, Pentakills, and unique champs need to be whole numbers.", ephemeral=True)
            return

        duration_seconds = voting.parse_duration(self.duration.value)
        if duration_seconds is None:
            await interaction.response.send_message("Use mm:ss for the total time, like `148:32`.", ephemeral=True)
            return
        picks["duration_seconds"] = duration_seconds

        problem = voting.validate_picks(picks)
        if problem:
            await interaction.response.send_message(f"{problem} Fix it and hit Submit again.", ephemeral=True)
            return

        if voting.entries_closed():
            await interaction.response.send_message("Entries closed while you were filling this out. No Honeyfruit was taken.", ephemeral=True)
            return

        balance = await get_wallet(interaction.user.id, interaction.guild_id)
        if balance < voting.ENTRY_FEE:
            await interaction.response.send_message(
                f"You need {voting.ENTRY_FEE} Honeyfruit to enter - you have {balance}.", ephemeral=True
            )
            return

        picks_json = json.dumps(picks)
        saved = await save_worlds_pick(interaction.user.id, interaction.guild_id, picks_json, int(time.time()))
        if not saved:
            await interaction.response.send_message("You've already entered the Worlds Pick'em in this server.", ephemeral=True)
            return

        new_balance = await adjust_wallet(interaction.user.id, interaction.guild_id, -voting.ENTRY_FEE)
        self.picks_view.stop()
        log(f"[WORLDS] {interaction.user} ({interaction.user.id}) entered pick'em in guild {interaction.guild_id}")

        await interaction.response.edit_message(
            content=f"✅ You're in! Paid {voting.ENTRY_FEE} Honeyfruit · balance: {new_balance}. Nobody else can see your picks.",
            embed=picks_embed(interaction.user, {"picks": picks_json}),
            view=None,
        )
        await interaction.followup.send(f"🏆 {interaction.user.mention} just locked in their Worlds Finals picks!")


class PicksView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900)
        self.picks: dict = {}
        self.numbers: dict = {}
        self.page = 0
        self.render()

    def header(self) -> str:
        return (
            f"🏆 **Worlds Finals Pick'em: GENG vs BLG** (page {self.page + 1}/{len(PAGES)})\n"
            f"Entry: {voting.ENTRY_FEE} Honeyfruit (only charged when you submit) · "
            f"{voting.POINTS_PER_CORRECT} per correct answer · "
            f"**{voting.GRAND_PRIZE}** for a perfect sheet, bonuses included.\n"
            f"Entries close <t:{voting.LOCK_TIMESTAMP}:F> (<t:{voting.LOCK_TIMESTAMP}:R>)."
        )

    def render(self):
        self.clear_items()
        for row, (key, placeholder, options) in enumerate(PAGES[self.page]):
            select = discord.ui.Select(
                placeholder=placeholder,
                row=row,
                options=[
                    discord.SelectOption(label=label, value=value, default=(self.picks.get(key) == value))
                    for label, value in options
                ],
            )
            select.callback = self.make_select_callback(key, select)
            self.add_item(select)

        if self.page > 0:
            back = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, row=4)
            back.callback = self.go_back
            self.add_item(back)
        if self.page < len(PAGES) - 1:
            next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, row=4)
            next_button.callback = self.go_next
            self.add_item(next_button)
        else:
            submit = discord.ui.Button(label="Enter numbers & submit", style=discord.ButtonStyle.success, row=4)
            submit.callback = self.open_modal
            self.add_item(submit)

    def make_select_callback(self, key: str, select: discord.ui.Select):
        async def callback(interaction: discord.Interaction):
            self.picks[key] = select.values[0]
            await interaction.response.defer()
        return callback

    def page_missing(self) -> list[str]:
        return [placeholder for key, placeholder, _ in PAGES[self.page] if key not in self.picks]

    async def go_back(self, interaction: discord.Interaction):
        self.page -= 1
        self.render()
        await interaction.response.edit_message(content=self.header(), view=self)

    async def go_next(self, interaction: discord.Interaction):
        missing = self.page_missing()
        if missing:
            await interaction.response.send_message("Still need: " + "; ".join(missing), ephemeral=True)
            return
        self.page += 1
        self.render()
        await interaction.response.edit_message(content=self.header(), view=self)

    async def open_modal(self, interaction: discord.Interaction):
        missing = self.page_missing()
        if missing:
            await interaction.response.send_message("Still need: " + "; ".join(missing), ephemeral=True)
            return
        await interaction.response.send_modal(NumbersModal(self))

class WorldsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="worldspicks", description="Enter the Worlds Finals Pick'em (1000 Honeyfruit) or view your picks")
    @app_commands.guild_only()
    async def worldspicks(self, interaction: discord.Interaction):
        existing = await get_worlds_pick(interaction.user.id, interaction.guild_id)
        if existing:
            await interaction.response.send_message(embed=picks_embed(interaction.user, existing), ephemeral=True)
            return

        if voting.entries_closed():
            await interaction.response.send_message(
                f"Worlds Pick'em entries closed <t:{voting.LOCK_TIMESTAMP}:R>.", ephemeral=True
            )
            return

        balance = await get_wallet(interaction.user.id, interaction.guild_id)
        if balance < voting.ENTRY_FEE:
            await interaction.response.send_message(
                f"You need {voting.ENTRY_FEE} Honeyfruit to enter - you have {balance}.", ephemeral=True
            )
            return

        view = PicksView()
        await interaction.response.send_message(view.header(), view=view, ephemeral=True)

    @app_commands.command(name="worldsresults", description="Owner only: enter the Worlds Finals results and pay out")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        series="Winner and series score",
        highest_kda="Player(s) with the highest average KDA - comma-separate ties",
        worst_kda="Player(s) with the worst average KDA - comma-separate ties",
        most_kills_player="Player(s) with the most kills in a single game - comma-separate ties",
        most_kills_count="How many kills that was",
        most_scuttles="Player(s) with the most Scuttle Crabs - comma-separate ties",
        nidalee_played="Was Nidalee picked at any point?",
        pentakills="Total Pentakills in the series (0 if none)",
        unique_champions="Unique champions picked + banned across the series",
        first_baron="Team that took the first Baron",
        total_duration="Total series time as mm:ss, e.g. 148:32",
        pentakill_players="Player(s) who got a Pentakill - leave empty if none",
    )
    @app_commands.choices(
        series=[app_commands.Choice(name=o, value=o) for o in voting.SERIES_OPTIONS],
        first_baron=[app_commands.Choice(name=t, value=t) for t in voting.TEAMS],
    )
    @app_commands.autocomplete(
        highest_kda=player_autocomplete,
        worst_kda=player_autocomplete,
        most_kills_player=player_autocomplete,
        most_scuttles=player_autocomplete,
        pentakill_players=player_autocomplete,
    )
    async def worldsresults(
        self,
        interaction: discord.Interaction,
        series: app_commands.Choice[str],
        highest_kda: str,
        worst_kda: str,
        most_kills_player: str,
        most_kills_count: int,
        most_scuttles: str,
        nidalee_played: bool,
        pentakills: int,
        unique_champions: int,
        first_baron: app_commands.Choice[str],
        total_duration: str,
        pentakill_players: str = "",
    ):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Only the bot owner can do that.", ephemeral=True)
            return

        if not voting.entries_closed():
            await interaction.response.send_message(
                f"Entries are still open until <t:{voting.LOCK_TIMESTAMP}:F> - can't pay out yet.", ephemeral=True
            )
            return

        errors = []
        lists = {}
        for key, text in (
            ("highest_kda", highest_kda),
            ("worst_kda", worst_kda),
            ("most_kills_players", most_kills_player),
            ("most_scuttles", most_scuttles),
            ("penta_players", pentakill_players),
        ):
            found, unknown = voting.parse_player_list(text)
            if unknown:
                errors.append(f"Not on the roster ({key}): {', '.join(unknown)}")
            lists[key] = found

        for key in ("highest_kda", "worst_kda", "most_kills_players", "most_scuttles"):
            if not lists[key]:
                errors.append(f"{key} needs at least one player.")
        if pentakills > 0 and not lists["penta_players"]:
            errors.append("You entered Pentakills but no pentakill_players.")
        if pentakills == 0 and lists["penta_players"]:
            errors.append("You entered pentakill_players but 0 Pentakills.")

        duration_seconds = voting.parse_duration(total_duration)
        if duration_seconds is None:
            errors.append("total_duration must be mm:ss, like 148:32.")

        if errors:
            await interaction.response.send_message("\n".join(errors), ephemeral=True)
            return

        results = {
            "series": series.value,
            "highest_kda": lists["highest_kda"],
            "worst_kda": lists["worst_kda"],
            "most_kills_players": lists["most_kills_players"],
            "most_kills_count": most_kills_count,
            "most_scuttles": lists["most_scuttles"],
            "nidalee": "Yes" if nidalee_played else "No",
            "pentakills": pentakills,
            "penta_players": lists["penta_players"],
            "unique_champs": unique_champions,
            "first_baron": first_baron.value,
            "duration_seconds": duration_seconds,
        }

        await interaction.response.defer(ephemeral=True, thinking=True)
        summary = await self.settle(results)
        await interaction.followup.send(summary, ephemeral=True)

    async def settle(self, results: dict) -> str:
        await set_bot_state(RESULTS_KEY, json.dumps(results))

        paid_count, total_paid, guild_ids = 0, 0, set()
        for row in await get_unpaid_worlds_picks():
            picks = json.loads(row["picks"])
            correct, payout, perfect = voting.calculate_payout(voting.score_picks(picks, results))
            if not await set_worlds_payout(row["discord_id"], row["guild_id"], correct, payout):
                continue
            if payout:
                await adjust_wallet(row["discord_id"], row["guild_id"], payout)
            paid_count += 1
            total_paid += payout
            guild_ids.add(row["guild_id"])
            if perfect:
                log(f"[WORLDS] PERFECT SHEET: {row['discord_id']} in guild {row['guild_id']}")

        for guild_id in guild_ids:
            await self.post_results(guild_id, results)

        log(f"[WORLDS] Settled {paid_count} entries for {total_paid} Honeyfruit")
        return f"Paid {paid_count} entries · {total_paid} Honeyfruit total."

    async def post_results(self, guild_id: int, results: dict) -> None:
        channel_id = await get_leaderboard_channel(guild_id)
        channel = self.bot.get_channel(channel_id) if channel_id else None
        if channel is None:
            log(f"[WORLDS] No leaderboard channel for guild {guild_id}, skipping results post")
            return

        rows = await get_worlds_picks_for_guild(guild_id)
        rows.sort(key=lambda r: (r["correct"] or 0), reverse=True)
        total_items = len(voting.SCORED_ITEMS)
        standings = [
            f"**{i}.** <@{r['discord_id']}> - {r['correct']}/{total_items} · +{r['payout']} 🍯"
            for i, r in enumerate(rows[:20], start=1)
        ]

        embed = discord.Embed(
            title="🏆 Worlds Finals Pick'em - Results",
            description="\n".join(voting.describe_results(results)),
            color=discord.Color.gold(),
        )
        embed.add_field(name="Standings", value="\n".join(standings) or "No entries.", inline=False)
        if any(r["payout"] and r["payout"] >= voting.GRAND_PRIZE for r in rows):
            embed.add_field(name="🍯 JACKPOT", value=f"Someone hit a perfect sheet and won the {voting.GRAND_PRIZE} grand prize!", inline=False)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException as e:
            log(f"[WORLDS] Failed to post results in guild {guild_id}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(WorldsCog(bot))