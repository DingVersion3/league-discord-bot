#Pulls fresh match history and current rank for every registered user, storing results in the DB. 
# This is what both the weekly scheduled task and (eventually) a manual admin trigger call into.
import asyncio
import time

from leaguebot.db import get_all_registered_users, save_match, save_rank
from leaguebot.riot_api import get_match_ids, get_match, get_rank, RiotAPIError

SECONDS_PER_WEEK = 7 * 24 * 60 * 60
MATCHES_TO_CHECK = 15  # how many recent match IDs to pull per user, per sync
_SYNC_LOCK = asyncio.Lock()


async def sync_all_users() -> dict:
    async with _SYNC_LOCK:
        return await _sync_all_users()


async def _sync_all_users() -> dict:
    # Returns a summary dict: {discord_id: {"matches_added": int, "error": str | None}}
    users = await get_all_registered_users()
    print(f"[SYNC] starting the syn for {len(users)} user(s)")
    now = int(time.time())
    cutoff = now - SECONDS_PER_WEEK
    summary = {}

    for user in users:
        discord_id = user["discord_id"]
        puuid = user["puuid"]
        added = 0
        print(f"[SYNC] Processing discord_id={discord_id}")

        try:
            match_ids = await get_match_ids(puuid, count=MATCHES_TO_CHECK)
            print(f"[SYNC]   got {len(match_ids)} match ids")
            for match_id in match_ids:
                print(f"[SYNC]   fetching match {match_id}")
                match = await get_match(match_id)
                print(f"[SYNC]   fetched match {match_id}")
                played_at = match["info"]["gameStartTimestamp"] // 1000  # ms -> s
                if played_at < cutoff:
                    continue  # older than a week, skip

                participant = next(
                    p for p in match["info"]["participants"] if p["puuid"] == puuid
                )
                print(f"[SYNC]   saving match {match_id}")
                added += await save_match(
                    discord_id=discord_id,
                    puuid=puuid,
                    match_id=match_id,
                    champion=participant["championName"],
                    win=participant["win"],
                    kills=participant["kills"],
                    deaths=participant["deaths"],
                    assists=participant["assists"],
                    damage=participant["totalDamageDealtToChampions"],
                    played_at=played_at,
                    duration=match["info"]["gameDuration"],
                    cs=participant["totalMinionsKilled"] + participant["neutralMinionsKilled"],
                    gold=participant["goldEarned"],
                    doubleKills=participant["doubleKills"],
                    tripleKills=participant["tripleKills"],
                    quadraKills=participant["quadraKills"],
                    pentaKills=participant["pentaKills"],
                )
                print(f"[SYNC]   saved match {match_id}")

            rank = await get_rank(puuid)
            if rank:
                await save_rank(
                    discord_id=discord_id,
                    puuid=puuid,
                    tier=rank["tier"],
                    rank=rank["rank"],
                    league_points=rank["league_points"],
                    updated_at=now,
                )

            summary[discord_id] = {"matches_added": added, "error": None}

        except RiotAPIError as e:
            summary[discord_id] = {"matches_added": added, "error": e.message}

    return summary
