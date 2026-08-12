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
import argparse
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from leaguebot.opgg_client import to_opgg_champion_format
from leaguebot.constants import BRACKETS, OPGG_POSITIONS, OPGG_POSITION_RESPONSE_NAMES
from leaguebot.helpers import log

OPGG_MCP_URL = "https://mcp-api.op.gg/mcp"
DATA_DIR = Path(__file__).parents[2] / "data"

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
        "role_rate": float(role_rate),
        "ban_rate": float(ban_rate),
        "kda": float(kda),
        "tier": int(tier),
        "rank": int(rank),
    }


async def _fetch_one(session: ClientSession, champion: str, position: str, tier: str) -> dict | None:
    try:
        result = await session.call_tool(
            "lol_get_champion_analysis",
            arguments={
                "champion": to_opgg_champion_format(champion),
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
    position_name = OPGG_POSITION_RESPONSE_NAMES[position]
    return _extract_position_stats(raw_text, position_name)

def _write(results: dict) -> None:
    with open(DATA_DIR / "opgg_tierlist.json", "w") as f:
        json.dump(results, f, indent=2)

def _load_existing(force: bool = False) -> dict:
    # Resume support: a run can die partway through (OP.GG 504s, network drops),
    # and re-fetching hours of already-cached data is wasteful. Reads whatever
    # the last run wrote so completed bracket/position combinations get skipped.
    if force:
        log("--force: ignoring existing cache, fetching everything")
        return {"generated_at": int(time.time()), "brackets": {}}

    path = DATA_DIR / "opgg_tierlist.json"
    if not path.exists():
        return {"generated_at": int(time.time()), "brackets": {}}

    try:
        with open(path) as f:
            existing = json.load(f)
    except (json.JSONDecodeError, OSError):
        log("existing cache unreadable, starting fresh")
        return {"generated_at": int(time.time()), "brackets": {}}

    log(f"resuming from existing cache (generated {existing.get('generated_at')})")
    return existing


async def main(force: bool = False) -> None:
    champion_names = _load_champion_names()
    log(f"Fetching {len(champion_names)} champions x {len(OPGG_POSITIONS)} lanes x {len(BRACKETS)} brackets...")

    results = _load_existing(force)
    results["generated_at"] = int(time.time())
    total_calls = 0
    total_hits = 0

    async with streamable_http_client(OPGG_MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            for tier in BRACKETS:
                results["brackets"].setdefault(tier, {})

                for position in OPGG_POSITIONS:
                    already = results["brackets"][tier].get(position)
                    if already:
                        log(f"  [{tier}] {position}: skipping, {len(already)} already cached")
                        continue

                    results["brackets"][tier][position] = {}
                    for champion in champion_names:
                        entry = await _fetch_one(session, champion, position, tier)
                        total_calls += 1
                        if entry:
                            results["brackets"][tier][position][champion] = entry
                            total_hits += 1
                        await asyncio.sleep(REQUEST_DELAY_SECONDS)

                    log(f"  [{tier}] {position}: {len(results['brackets'][tier][position])} champions found")

                    # Write after each position rather than each bracket, so a
                    # failure costs at most one lane's worth of fetching.
                    _write(results)

    # Playrate-weighted role averages, so popular champions count more than
    # rarely-played ones when establishing what's "normal" for a role.
    for tier in BRACKETS:
        results["brackets"][tier]["_role_averages"] = {}
        for position in OPGG_POSITIONS:
            champs = results["brackets"][tier].get(position, {})
            total_play = sum(c["play"] for c in champs.values())
            if total_play <= 0:
                continue
            results["brackets"][tier]["_role_averages"][position] = {
                "kda": sum(c["kda"] * c["play"] for c in champs.values()) / total_play,
                "win_rate": sum(c["win_rate"] * c["play"] for c in champs.values()) / total_play,
                "sample_games": total_play,
            }

    _write(results)

    log(f"done. {total_hits}/{total_calls} calls returned usable data this run.")
    log(f"saved to {DATA_DIR / 'opgg_tierlist.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cache OP.GG tier data. Resumes from an existing cache unless --force.")
    parser.add_argument("--force", action="store_true", help="ignore the existing cache and re-fetch everything")
    args = parser.parse_args()
    asyncio.run(main(args.force))