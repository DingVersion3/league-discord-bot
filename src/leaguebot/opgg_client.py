# Shared OP.GG MCP client. Handles lane matchup guidance and lane tier lists
# via OP.GG's public MCP server. Mirrors riot_api.py's structure/error handling.
#
# Meta/off-meta classification:
#   OP.GG's MCP tier-list data only exposes pick_rate rounded to the nearest
#   whole percent (e.g. "0.01" could really be anywhere from 0.51% to 1.49%).
#   To keep the meta/off-meta boundary unambiguous despite that rounding, the
#   cutoff is set at 2% rather than 1% -- anything that rounds down to "1%"
#   or lower is confidently below a 2% threshold either way.
#
#   - meta:     pick_rate > META_PICK_RATE_THRESHOLD -> shown by default
#   - off-meta: pick_rate <= META_PICK_RATE_THRESHOLD, but has real (nonzero)
#               play data -> shown only when include_off_meta=True
#   - excluded: zero games played -> never shown, regardless of toggle
import ast
import json
import re

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

OPGG_MCP_URL = "https://mcp-api.op.gg/mcp"

META_PICK_RATE_THRESHOLD = 0.02  # 2%, accounts for OP.GG's whole-percent rounding


class OpggError(Exception):
    # Raised when the OP.GG MCP server returns an error or unusable response.
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def _call_tool(tool_name: str, arguments: dict) -> str:
    # Returns the raw text content from a tool call, or raises OpggError.
    async with streamable_http_client(OPGG_MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            try:
                result = await session.call_tool(tool_name, arguments=arguments)
            except Exception as e:
                raise OpggError(f"OP.GG request failed: {e}") from e

            if result.isError:
                raise OpggError(f"OP.GG returned an error: {result.content}")
            if not result.content:
                raise OpggError("OP.GG returned no content.")

            return result.content[0].text


def _parse_repr_list(raw_text: str, class_name: str, field_names: list[str]) -> list[dict]:
    # Parses OP.GG's non-JSON Python-repr-style responses, e.g.:
    #   Mid("Ahri", 1, 0.51, 0.09, 103491, 2)
    # into a list of dicts using the field names in the order they were requested.
    pattern = rf'{class_name}\((.*?)\)'
    matches = re.findall(pattern, raw_text)

    entries = []
    for match in matches:
        try:
            values = ast.literal_eval(f"({match})")
        except (ValueError, SyntaxError):
            continue
        if not isinstance(values, tuple):
            values = (values,)
        entries.append(dict(zip(field_names, values)))
    return entries


async def get_lane_tier_list(position: str, include_off_meta: bool = False) -> list[dict]:
    # position: "top" | "mid" | "jungle" | "adc" | "support" | "all"
    raw_text = await _call_tool(
        "lol_list_lane_meta_champions",
        arguments={
            "position": position,
            "desired_output_fields": [
                f"data.positions.{position}[].{{champion,tier,win_rate,pick_rate,play,rank}}"
            ],
        },
    )

    class_name = position.capitalize()  # "mid" -> "Mid", matching OP.GG's response class name
    entries = _parse_repr_list(
        raw_text, class_name, ["champion", "tier", "win_rate", "pick_rate", "play", "rank"]
    )

    if not entries:
        raise OpggError("Couldn't parse tier list response.")

    filtered = []
    for e in entries:
        games = e.get("play", 0)
        pick_rate = e.get("pick_rate", 0)

        if games <= 0:
            continue  # only exclude genuinely zero-game entries

        is_meta = pick_rate > META_PICK_RATE_THRESHOLD
        if is_meta or include_off_meta:
            e["is_meta"] = is_meta
            filtered.append(e)

    filtered.sort(key=lambda e: e["rank"])
    return filtered


async def get_lane_matchup(
    my_champion: str, opponent_champion: str, position: str, include_off_meta: bool = False
) -> dict:
    raw_text = await _call_tool(
        "lol_get_lane_matchup_guide",
        arguments={
            "my_champion": my_champion.upper(),
            "opponent_champion": opponent_champion.upper(),
            "position": position,
        },
    )

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise OpggError("Couldn't parse matchup response.") from e

    data = parsed.get("data", {})
    counters = data.get("summary", {}).get("positions", [{}])[0].get("counters", [])

    # cross-reference each counter's real pick rate against the current lane
    # tier list, so we can classify meta vs. off-meta the same way /tierlist does
    try:
        tier_list = await get_lane_tier_list(position, include_off_meta=True)
        pick_rate_by_champion = {e["champion"]: e["pick_rate"] for e in tier_list}
    except OpggError:
        pick_rate_by_champion = {}

    classified = []
    for c in counters:
        champion_name = c["champion_name"]
        games = c.get("play", 0)
        if games <= 0:
            continue  # only exclude genuinely zero-game entries

        pick_rate = pick_rate_by_champion.get(champion_name, 0)
        is_meta = pick_rate > META_PICK_RATE_THRESHOLD

        if is_meta or include_off_meta:
            classified.append({
                "champion": champion_name,
                "play": games,
                "win_rate": c["win"] / games if games else None,
                "is_meta": is_meta,
            })

    classified.sort(key=lambda c: c["play"], reverse=True)

    return {
        "tip": data.get("opponent_champion_tip"),
        "lane_advantage": data.get("lane_advantage_champion"),
        "play_style": data.get("recommended_play_style"),
        "top_counters": classified[:5],
    }