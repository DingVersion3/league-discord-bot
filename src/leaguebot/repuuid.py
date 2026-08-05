"""
One-off: re-resolves every registered user's PUUID under the current API key.

PUUIDs are encrypted per API key, so switching keys invalidates every stored
one -- Riot returns "Exception decrypting" on any call using an old PUUID.
This looks each user up again by their stored Riot ID and writes the new value.

Match history is unaffected -- the matches table joins on discord_id, not puuid.

Usage (from project root):
    python -m leaguebot.repuuid
"""
import asyncio

import aiosqlite

from leaguebot.db import _connect, get_all_registered_users
from leaguebot.riot_api import get_puuid, RiotAPIError
from leaguebot.helpers import log


async def update_puuid(discord_id: int, puuid: str) -> None:
    async with _connect() as db:
        await db.execute(
            "UPDATE users SET puuid = ? WHERE discord_id = ?", (puuid, discord_id)
        )
        await db.commit()


async def main() -> None:
    users = await get_all_registered_users()
    log(f"re-resolving PUUIDs for {len(users)} user(s)")

    updated = 0
    failed = []

    for user in users:
        discord_id = user["discord_id"]
        game_name = user["game_name"]
        tag_line = user["tag_line"]
        regional_route = user["regional_route"] or "americas"
        old_puuid = user["puuid"]

        try:
            new_puuid = await get_puuid(game_name, tag_line, regional_route=regional_route)
        except RiotAPIError as e:
            failed.append((f"{game_name}#{tag_line}", e.message))
            log(f"  FAILED {game_name}#{tag_line}: {e.message}")
            continue

        if new_puuid == old_puuid:
            log(f"  unchanged {game_name}#{tag_line} (already current)")
            continue

        await update_puuid(discord_id, new_puuid)
        updated += 1
        log(f"  updated {game_name}#{tag_line}")

        await asyncio.sleep(1.3)  # stay under the rate limit

    log(f"done: {updated} updated, {len(failed)} failed")
    for name, reason in failed:
        log(f"  {name}: {reason}")


if __name__ == "__main__":
    asyncio.run(main())