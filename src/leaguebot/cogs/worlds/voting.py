import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

ENTRY_FEE = 1000
POINTS_PER_CORRECT = 10000
GRAND_PRIZE = 1000000
LOCK_TIME = datetime(2026, 11, 14, 10, 59, tzinfo=ZoneInfo("America/Los_Angeles"))
LOCK_TIMESTAMP = int(LOCK_TIME.timestamp())
TEAMS = ["GENG", "BLG"]
ROSTERS = {
    "GENG": ["Kiin", "Canyon", "Chovy", "Ruler", "Duro"],
    "BLG": ["Bin", "Xun", "Knight", "Viper", "ON"],
}
PLAYERS = ROSTERS["GENG"] + ROSTERS["BLG"]
PLAYER_TEAM = {player: team for team, roster in ROSTERS.items() for player in roster}
SERIES_OPTIONS = [f"{team} {score}" for team in TEAMS for score in ("3-0", "3-1", "3-2")]
DURATION_LINE_MINUTES = 145
NO_PENTA = "None"
SCORED_ITEMS = {
    "series": ("1. Series winner & score", False),
    "highest_kda": ("2. Highest average KDA", False),
    "worst_kda": ("3. Worst average KDA", False),
    "most_kills": ("4. Most kills in a single game", False),
    "most_scuttles": ("5. Most Scuttle Crabs", False),
    "nidalee": ("6. Nidalee played?", False),
    "pentakills": ("7. Number of Pentakills", False),
    "penta_player": ("7. BONUS: Who gets the Pentakill", True),
    "unique_champs": ("8. Unique champions picked + banned", False),
    "first_baron": ("9. First Baron", False),
    "duration_ou": ("10. Total duration O/U 145", False),
    "duration_exact": ("10. BONUS: Exact total duration", True),
}
DURATION_PATTERN = re.compile(r"^\s*(\d{1,3}):([0-5]\d)\s*$")

def entries_closed() -> bool:
    return time.time() >= LOCK_TIMESTAMP

def parse_duration(text: str) -> int | None:
    # "152:07" -> 9127 seconds. Minutes can go past 60 since it's the whole series.
    match = DURATION_PATTERN.match(text or "")
    if not match:
        return None
    return int(match.group(1)) * 60 + int(match.group(2))

def format_duration(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"

def resolve_player(name: str) -> str | None:
    cleaned = name.strip().lower()
    for player in PLAYERS:
        if player.lower() == cleaned:
            return player
    return None

def parse_player_list(text: str) -> tuple[list[str], list[str]]:
    found, unknown = [], []
    for part in (text or "").split(","):
        if not part.strip():
            continue
        player = resolve_player(part)
        if player is None:
            unknown.append(part.strip())
        elif player not in found:
            found.append(player)
    return found, unknown

def player_label(player: str) -> str:
    if player == NO_PENTA:
        return "No Pentakill"
    return f"{player} ({PLAYER_TEAM[player]})"

def validate_picks(picks: dict) -> str | None:
    if not 0 <= picks["most_kills_count"] <= 60:
        return "Most kills in a game should be between 0 and 60."
    if not 0 <= picks["pentakills"] <= 25:
        return "Pentakill count should be between 0 and 25."
    if not 20 <= picks["unique_champs"] <= 100:
        return "Unique champions has to be between 20 (one game's picks + bans) and 100 (five games, no repeats)."
    if picks["pentakills"] == 0 and picks["penta_player"] != NO_PENTA:
        return f"You picked {picks['penta_player']} for the Pentakill bonus but said there'd be 0 Pentakills."
    if picks["pentakills"] > 0 and picks["penta_player"] == NO_PENTA:
        return "You said there'd be Pentakills but picked No Pentakill for the bonus."
    line = DURATION_LINE_MINUTES * 60
    seconds = picks["duration_seconds"]
    if seconds != line and (seconds > line) != (picks["duration_ou"] == "Over"):
        return f"Your exact time ({format_duration(seconds)}) contradicts your {picks['duration_ou']} {DURATION_LINE_MINUTES} pick."
    return None


def score_picks(picks: dict, results: dict) -> dict[str, bool]:
    actual_seconds = results["duration_seconds"]
    line_seconds = DURATION_LINE_MINUTES * 60
    if actual_seconds == line_seconds:
        duration_ou_correct = True
    else:
        actual_side = "Over" if actual_seconds > line_seconds else "Under"
        duration_ou_correct = picks["duration_ou"] == actual_side

    if results["pentakills"] == 0:
        penta_player_correct = picks["penta_player"] == NO_PENTA
    else:
        penta_player_correct = picks["penta_player"] in results["penta_players"]

    return {
        "series": picks["series"] == results["series"],
        "highest_kda": picks["highest_kda"] in results["highest_kda"],
        "worst_kda": picks["worst_kda"] in results["worst_kda"],
        "most_kills": (
            picks["most_kills_player"] in results["most_kills_players"]
            and picks["most_kills_count"] == results["most_kills_count"]
        ),
        "most_scuttles": picks["most_scuttles"] in results["most_scuttles"],
        "nidalee": picks["nidalee"] == results["nidalee"],
        "pentakills": picks["pentakills"] == results["pentakills"],
        "penta_player": penta_player_correct,
        "unique_champs": picks["unique_champs"] == results["unique_champs"],
        "first_baron": picks["first_baron"] == results["first_baron"],
        "duration_ou": duration_ou_correct,
        "duration_exact": picks["duration_seconds"] == actual_seconds,
    }


def calculate_payout(scored: dict[str, bool]) -> tuple[int, int, bool]:
    correct = sum(scored.values())
    perfect = correct == len(SCORED_ITEMS)
    payout = correct * POINTS_PER_CORRECT + (GRAND_PRIZE if perfect else 0)
    return correct, payout, perfect


def describe_picks(picks: dict) -> list[str]:
    return [
        f"**1.** {picks['series']}",
        f"**2.** Highest KDA: {player_label(picks['highest_kda'])}",
        f"**3.** Worst KDA: {player_label(picks['worst_kda'])}",
        f"**4.** Most kills in a game: {player_label(picks['most_kills_player'])} with {picks['most_kills_count']}",
        f"**5.** Most Scuttles: {player_label(picks['most_scuttles'])}",
        f"**6.** Nidalee played: {picks['nidalee']}",
        f"**7.** Pentakills: {picks['pentakills']} · Bonus: {player_label(picks['penta_player'])}",
        f"**8.** Unique champs picked + banned: {picks['unique_champs']}",
        f"**9.** First Baron: {picks['first_baron']}",
        f"**10.** Duration: {picks['duration_ou']} {DURATION_LINE_MINUTES} · Bonus: {format_duration(picks['duration_seconds'])}",
    ]

def describe_results(results: dict) -> list[str]:
    def names(players: list[str]) -> str:
        return ", ".join(player_label(p) for p in players)

    pentas = names(results["penta_players"]) if results["pentakills"] else "None"
    return [
        f"**1.** {results['series']}",
        f"**2.** Highest KDA: {names(results['highest_kda'])}",
        f"**3.** Worst KDA: {names(results['worst_kda'])}",
        f"**4.** Most kills in a game: {names(results['most_kills_players'])} with {results['most_kills_count']}",
        f"**5.** Most Scuttles: {names(results['most_scuttles'])}",
        f"**6.** Nidalee played: {results['nidalee']}",
        f"**7.** Pentakills: {results['pentakills']} · {pentas}",
        f"**8.** Unique champs picked + banned: {results['unique_champs']}",
        f"**9.** First Baron: {results['first_baron']}",
        f"**10.** Total duration: {format_duration(results['duration_seconds'])}",
    ]