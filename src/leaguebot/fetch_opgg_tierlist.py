# Fetches per-champion, per-lane, per-rank-bracket tier data from OP.GG's MCP
# server and caches it locally in data/opgg_tierlist.json.

# lol_get_champion_analysis returns a Python-repr-style response (not JSON),
# nested as: Data -> Summary -> positions[] -> Position("NAME", Stats(...), [...]).
# Stats itself nests a TierData(tier, rank, rank_prev, rank_prev_patch) tuple.
# This script parses that specific structure directly with regex rather than
# relying on the tool's desired_output_fields filtering, since that filtering
# doesn't support this level of nesting (confirmed via the tool's own field
# diagnostics hint).

# Usage:
#     python src/leaguebot/fetch_opgg_tierlist.py

import asyncio
import json
import re
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

OPGG_MCP_URL = "https://mcp-api.op.gg/mcp"
DATA_DIR = Path(__file__).parents[2] / "data"

POSITIONS = ["top", "jungle", "mid", "adc", "support"]
POSITION_NAME_MAP = {"top": "TOP", "jungle": "JUNGLE", "mid": "MID", "adc": "ADC", "support": "SUPPORT"}
BRACKETS = ["gold_plus", "diamond_plus", "all"]
GAME_MODE = "RANKED"

REQUEST_DELAY_SECONDS = 0.15


def _load_champion_names() -> list[str]:
    with open(DATA_DIR / "champions.json") as f:
        data = json.load(f)
        return list(data["champions"].values())


def _extract_position_stats(raw_text: str, position_name: str) -> dict | None:
    # Finds Position("TOP", Stats(play,win_rate,pick_rate,role_rate,ban_rate,kda,
    # TierData(tier,rank,rank_prev,rank_prev_patch)), [...]) for the given position,
    # and pulls out just the fields we care about.
    pattern = (
        rf'Position\("{position_name}",\s*Stats\('
        r'([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),([\d.]+),'
        r'TierData\((\d+),(\d+),(\d+),(\d+)\)\)'
    )
    match = re.search(pattern, raw_text)
    if not match:
        return None

    play, win_rate, pick_rate, role_rate, ban_rate, kda, tier, rank, rank_prev, rank_prev_patch = match.groups()

    return {
        "play": int(play),
        "win_rate": float(win_rate),
        "pick_rate": float(pick_rate),
        "ban_rate": float(ban_rate),
        "tier": int(tier),
        "rank": int(rank),
    }


async def _fetch_one(session: ClientSession, champion: str, position: str, tier: str) -> dict | None:
    try:
        result = await session.call_tool(
            "lol_get_champion_analysis",
            arguments={
                "champion": champion.upper(),
                "position": position,
                "tier": tier,
                "game_mode": GAME_MODE,
                "desired_output_fields": [],  # full response -- filtering doesn't reach this deep
            },
        )
    except Exception:
        return None

    if result.isError or not result.content:
        return None

    raw_text = result.content[0].text
    position_name = POSITION_NAME_MAP[position]
    return _extract_position_stats(raw_text, position_name)


async def main() -> None:
    champion_names = _load_champion_names()
    print(f"Fetching {len(champion_names)} champions x {len(POSITIONS)} lanes x {len(BRACKETS)} brackets...")

    results = {"generated_at": int(time.time()), "brackets": {}}
    total_calls = 0
    total_hits = 0

    async with streamable_http_client(OPGG_MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            for tier in BRACKETS:
                results["brackets"][tier] = {}
                for position in POSITIONS:
                    results["brackets"][tier][position] = {}
                    for champion in champion_names:
                        entry = await _fetch_one(session, champion, position, tier)
                        total_calls += 1
                        if entry:
                            results["brackets"][tier][position][champion] = entry
                            total_hits += 1
                        await asyncio.sleep(REQUEST_DELAY_SECONDS)

                    print(f"  [{tier}] {position}: {len(results['brackets'][tier][position])} champions found")

    with open(DATA_DIR / "opgg_tierlist.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone. {total_hits}/{total_calls} calls returned usable data.")
    print(f"Saved to {DATA_DIR / 'opgg_tierlist.json'}")


if __name__ == "__main__":
    asyncio.run(main())