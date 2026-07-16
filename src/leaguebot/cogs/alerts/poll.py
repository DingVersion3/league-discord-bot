# background listener that watches for new match results per-user,
# independent of leaderboards weekly sync. only pulls each users single 
# most recent match per tick, attempting to be cheap on the RIOT API rate limit

from leaguebot.db import get_all_registered_users, get_streak, set_last_match_id, get_leaderboard_channel
from leaguebot.riot_api import get_match_ids, get_match, RiotAPIError
from . import alerts

INTERVAL = 90


async def check_for_new_results(bot) -> None:
    users = await get_all_registered_users()

    for user in users:
        discord_id = user["discord_id"]
        puuid = user["puuid"]
        regional_route = user["regional_route"]

        try:
            match_ids = await get_match_ids(puuid, regional_route=regional_route, count=1)
        except RiotAPIError as e:
            print(f"[ALERTS] failed to fetch latest match for {discord_id}: {e.message}")
            continue

        if not match_ids:
            continue
        latest_match_id = match_ids[0]

        streak_row = await get_streak(discord_id)
        last_seen = streak_row["last_match_id"] if streak_row else None

        if last_seen is None:
            # First time we've seen this user — baseline without alerting,
            # so we don't retroactively fire on a game played before they registered.
            await set_last_match_id(discord_id, latest_match_id)
            continue

        if latest_match_id == last_seen:
            continue  # no new game since last check

        try:
            match = await get_match(latest_match_id, regional_route=regional_route)
        except RiotAPIError as e:
            print(f"[ALERTS] failed to fetch match details for {discord_id}: {e.message}")
            continue

        participant = next(p for p in match["info"]["participants"] if p["puuid"] == puuid)
        won = participant["win"]

        await set_last_match_id(discord_id, latest_match_id)
        alert_msg = await alerts.process_result(discord_id, won)

        if alert_msg:
            await post_alert(bot, discord_id, alert_msg)


async def post_alert(bot, discord_id: int, message: str) -> None:
    for guild in bot.guilds:
        if guild.get_member(discord_id) is None:
            continue
        channel_id = await get_leaderboard_channel(guild.id)
        if not channel_id:
            continue
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(f"<@{discord_id}> {message}")