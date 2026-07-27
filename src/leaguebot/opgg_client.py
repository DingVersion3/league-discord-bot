# Shared OP.GG client. Tier/rank/pick-rate data comes from a locally cached
# JSON file (data/opgg_tierlist.json, built by fetch_opgg_tierlist.py -- run
# manually after each patch, same workflow as fetch_ddragon.py). Lane matchup
# guidance (tips, lane advantage, play style) still requires a live MCP call,
# since that's a pairwise champion-vs-champion lookup that can't be bulk-cached
# the way the tier list can.
#
# Meta/off-meta classification:
#   - meta:     pick_rate > META_PICK_RATE_THRESHOLD -> shown by default
#   - off-meta: pick_rate <= META_PICK_RATE_THRESHOLD, but has real (nonzero)
#               play data -> shown only when include_off_meta=True
#   - excluded: zero games played -> never shown, regardless of toggle
import json
import re
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from leaguebot.constants import CHAMPION_ALIASES

OPGG_MCP_URL = "https://mcp-api.op.gg/mcp"
DATA_DIR = Path(__file__).parents[2] / "data"

META_PICK_RATE_THRESHOLD = 0.02  # 2%, accounts for OP.GG's whole-percent rounding in the cached data

DEFAULT_BRACKET = "gold_plus"
VALID_BRACKETS = {"gold_plus", "diamond_plus", "all"}


class OpggError(Exception):
    # Raised when OP.GG data is unavailable or unusable.
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _load_tierlist_cache() -> dict:
    path = DATA_DIR / "opgg_tierlist.json"
    if not path.exists():
        raise OpggError(
            "No cached tier list data found. Run fetch_opgg_tierlist.py after the next patch."
        )
    with open(path) as f:
        return json.load(f)

def _resolve_champion(name: str) -> str:
    # Maps loose user input ("dr mundo", "Dr. Mundo") to OP.GG's expected
    # UPPER_SNAKE_CASE format (e.g. "DR_MUNDO").
    with open(DATA_DIR / "champions.json") as f:
        champions = json.load(f)["champions"]

    normalized = re.sub(r"[^a-z]", "", name.lower())

    # aliases resolve to a display name, then goes through normal matching
    target = CHAMPION_ALIASES.get(normalized)
    if target:
        normalized = re.sub(r"[^a-z0-9]", "", target.lower())

    for champ_id, display_name in champions.items():
        if re.sub(r"[^a-z0-9]", "", display_name.lower()) == normalized:
            # Convert the display name to UPPER_SNAKE_CASE: strip punctuation,
            # then join words with underscores. "Dr. Mundo" -> "DR_MUNDO"
            words = re.sub(r"[^a-zA-Z\s]", "", display_name).split()
            return "_".join(words).upper()

    raise OpggError(f"Unknown champion: {name}")


def get_lane_tier_list(position: str, bracket: str = DEFAULT_BRACKET, include_off_meta: bool = False) -> list[dict]:
    # position: "top" | "jungle" | "mid" | "adc" | "support"
    if bracket not in VALID_BRACKETS:
        raise OpggError(f"Unknown bracket '{bracket}'. Must be one of: {', '.join(VALID_BRACKETS)}")

    cache = _load_tierlist_cache()
    champions = cache.get("brackets", {}).get(bracket, {}).get(position, {})

    if not champions:
        raise OpggError(f"No cached data for {position} in bracket {bracket}.")

    filtered = []
    for champion, stats in champions.items():
        if stats.get("play", 0) <= 0:
            continue  # only exclude genuinely zero-game entries

        is_meta = stats.get("pick_rate", 0) > META_PICK_RATE_THRESHOLD
        if is_meta or include_off_meta:
            filtered.append({
                "champion": champion,
                "tier": stats.get("tier"),
                "rank": stats.get("rank"),
                "win_rate": stats.get("win_rate"),
                "pick_rate": stats.get("pick_rate"),
                "is_meta": is_meta,
            })

    filtered.sort(key=lambda e: e["rank"] if e["rank"] is not None else 9999)
    return filtered


async def _call_tool(tool_name: str, arguments: dict) -> str:
    # Live MCP call -- only used for lane matchup guidance, which isn't cached.
    try:
        async with streamable_http_client(OPGG_MCP_URL) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)

                if result.isError:
                    raise OpggError(f"OP.GG returned an error: {result.content}")
                if not result.content:
                    raise OpggError("OP.GG returned no content.")

                return result.content[0].text
    except BaseException as e:
        raise OpggError(_unwrap(e)) from e


async def get_lane_matchup(
    my_champion: str,
    opponent_champion: str,
    position: str,
) -> dict:
    # Tip/lane-advantage/play-style come from a live call (not cached).
    # Counters are split into weak/strong matchups by win rate.
    my_resolved = _resolve_champion(my_champion)
    opponent_resolved = _resolve_champion(opponent_champion)
    print(f"[DEBUG] sending champions: {my_resolved} vs {opponent_resolved}")

    raw_text = await _call_tool(
        "lol_get_lane_matchup_guide",
        arguments={
            "my_champion": _resolve_champion(my_champion),
            "opponent_champion": _resolve_champion(opponent_champion),
            "position": position,
        },
    )

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise OpggError("Couldn't parse matchup response.") from e

    data = parsed.get("data", {})
    counters = data.get("counters", [])

    # OP.GG's `win` field counts MY champion's wins in that matchup, so
    # win/play is my win rate: under 50% means I lose the lane, over means I win it.
    rated = []
    for c in counters:
        games = c.get("play", 0)
        if games <= 0:
            continue
        rated.append({
            "champion": c["champion_name"],
            "play": games,
            "win_rate": c["win"] / games,
        })

    weak_against = sorted([c for c in rated if c["win_rate"] < 0.5], key=lambda c: c["win_rate"])[:5]
    strong_against = sorted([c for c in rated if c["win_rate"] >= 0.5], key=lambda c: c["win_rate"], reverse=True)[:5]

    return {
        "tip": data.get("opponent_champion_tip"),
        "lane_advantage": data.get("lane_advantage_champion"),
        "play_style": data.get("recommended_play_style"),
        "weak_against": weak_against,
        "strong_against": strong_against,
    }