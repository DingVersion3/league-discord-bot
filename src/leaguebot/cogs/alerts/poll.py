# background listener that watches for new match results per-user,
# independent of leaderboards weekly sync. only pulls each users single 
# most recent match per tick, attempting to be cheap on the RIOT API rate limit

import time

from leaguebot.db import get_all_registered_users, get_streak, set_last_match_id, get_leaderboard_channel,get_rank as db_get_rank, save_rank, get_recent_matches, get_open_bet
from leaguebot.riot_api import get_match_ids, get_match, get_rank as riot_get_rank, RiotAPIError
from leaguebot.cogs.leaderboard.board import SECONDS_PER_WEEK
from leaguebot.cogs.betting import betting as betting_logic
from . import alerts

INTERVAL = 90


async def check_for_new_results(bot) -> None:
    users = await get_all_registered_users()

    for user in users:
        discord_id = user["discord_id"]
        puuid = user["puuid"]
        regional_route = user["regional_route"]
        platform_route = user["platform_route"]

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

        # check for a rank change since a new game has been confirmed
        try:
            new_rank = await riot_get_rank(puuid, platform_route=platform_route)
        except RiotAPIError as e:
            print(f"[ALERTS] failed to fetch rank for {discord_id}: {e.message}")
            continue

        if new_rank:
            old_rank = await db_get_rank(discord_id)
            rank_msg = alerts.get_rank_change_message(old_rank, new_rank)
            await save_rank(
                discord_id=discord_id, puuid=puuid,
                tier=new_rank["tier"], rank=new_rank["rank"],
                league_points=new_rank["league_points"], updated_at=int(time.time())
            )
            if rank_msg:
                await post_alert(bot, discord_id, rank_msg)

        # check for a stat spike vs. their own recent average
        since = int(time.time()) - SECONDS_PER_WEEK
        previous_matches = await get_recent_matches(discord_id, since)
        new_match_row = {
            "cs": participant["totalMinionsKilled"] + participant["neutralMinionsKilled"],
            "duration": match["info"]["gameDuration"],
            "damage": participant["totalDamageDealtToChampions"],
            "team_damage": sum(
                p["totalDamageDealtToChampions"] for p in match["info"]["participants"]
                if p["teamId"] == participant["teamId"]
            ),
            "position": participant["teamPosition"],
        }
        spike_msg = alerts.get_spike_message(new_match_row, previous_matches)
        if spike_msg:
            await post_alert(bot, discord_id, spike_msg)

        # resolve any open bet on this player's game
        open_bet = await get_open_bet(discord_id)
        if open_bet:
            results = await betting_logic.resolve(open_bet["bet_id"], won)
            if results:
                outcome = "won" if won else "lost"
                lines = [
                    f"<@{r['discord_id']}> {'won' if r['won'] else 'lost'} {r['amount']} Honeyfruit"
                    + (f" (+{r['payout']})" if r['won'] else "")
                    for r in results
                ]
                summary = f"🎲 Bet resolved — <@{discord_id}> {outcome} their game!\n" + "\n".join(lines)
                await post_alert(bot, discord_id, summary)


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