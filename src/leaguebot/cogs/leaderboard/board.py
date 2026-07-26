# Builds leaderboard embeds from stored match/rank data. Shared by the on-demand /leaderboard command and the weekly auto-post task.

import time

import discord

from collections import defaultdict
from leaguebot.db import get_recent_matches, get_rank, get_registered_users_in_guild, get_registered_user, get_duo_matches, get_all_wallets 
from leaguebot.constants import SECONDS_PER_WEEK, TIER_ORDER, DIVISION_ORDER, MIN_GAMES_FOR_PERSONAL_WEIGHT, RIOT_TO_OPGG_POSITION
from leaguebot.opgg_client import get_lane_tier_list, OpggError


def _rank_sort_key(rank: dict) -> tuple:
    tier_index = TIER_ORDER.index(rank["tier"]) if rank["tier"] in TIER_ORDER else -1
    division_index = DIVISION_ORDER.get(rank["rank"], 0)
    return (tier_index, division_index, rank["league_points"] or 0)


async def _weekly_stats_for_user(discord_id: int) -> dict | None:
    since = int(time.time()) - SECONDS_PER_WEEK
    matches = await get_recent_matches(discord_id, since)
    if not matches:
        return None

    games = len(matches)
    wins = sum(m["win"] for m in matches)
    total_kills = sum(m["kills"] for m in matches)
    total_deaths = sum(m["deaths"] for m in matches)
    total_assists = sum(m["assists"] for m in matches)
    total_doubleKills = sum(m["doubleKills"] for m in matches)
    total_tripleKills = sum(m["tripleKills"] for m in matches)
    total_quadraKills = sum(m["quadraKills"] for m in matches)
    total_pentaKills = sum(m["pentaKills"] for m in matches)

    return {
        "games": games,
        "wins": wins,
        "win_rate": wins / games,
        "avg_kda": (total_kills + total_assists) / max(total_deaths, 1),
        "double_kills": total_doubleKills,
        "triple_kills": total_tripleKills,
        "quadra_kills": total_quadraKills,
        "penta_kills": total_pentaKills,
    }
# finds the champion you lost to the most for the lane you played
async def get_nemesis(discord_id: int, since_timestamp: int) -> dict | None:
    matches = await get_recent_matches(discord_id, since_timestamp)
    losses_by_enemy = defaultdict(int)
    for m in matches:
        if not m["win"] and m["enemy_champion"]:
            losses_by_enemy[m["enemy_champion"]] += 1
    if not losses_by_enemy:
        return None
    champ, count = max(losses_by_enemy.items(), key=lambda x: x[1])
    return {"champion": champ, "losses": count}

async def get_champion_recommendations(discord_id: int, position: str, champion_filter: list[str] | None = None) -> list[dict]:
    matches = await get_recent_matches(discord_id, 0)  # 0 = all-time, since match data isn't purged

    position_matches = [m for m in matches if m["position"] == position]
    if champion_filter:
        champion_filter_lower = {c.lower() for c in champion_filter}
        position_matches = [m for m in position_matches if m["champion"].lower() in champion_filter_lower]

    by_champion = defaultdict(list)
    for m in position_matches:
        by_champion[m["champion"]].append(m)

    personal_stats = {}
    for champion, champ_matches in by_champion.items():
        wins = sum(m["win"] for m in champ_matches)
        personal_stats[champion] = {
            "win_rate": wins / len(champ_matches),
            "games": len(champ_matches),
        }

    # pull current meta tier list for this lane, fold in as a fallback/blend signal
    meta_by_champion = {}
    opgg_position = RIOT_TO_OPGG_POSITION.get(position)
    if opgg_position:
        try:
            tier_list = await get_lane_tier_list(opgg_position)
            meta_by_champion = {entry["champion"]: entry["win_rate"] for entry in tier_list}
        except OpggError:
            pass  # degrade gracefully — blend just uses personal data alone

    all_champions = set(personal_stats) | set(meta_by_champion)
    if champion_filter:
        champion_filter_lower = {c.lower() for c in champion_filter}
        all_champions = {c for c in all_champions if c.lower() in champion_filter_lower}

    results = []
    for champion in all_champions:
        personal = personal_stats.get(champion)
        meta_win_rate = meta_by_champion.get(champion)

        personal_win_rate = personal["win_rate"] if personal else None
        personal_games = personal["games"] if personal else 0

        if personal_win_rate is not None and meta_win_rate is not None:
            confidence = min(personal_games / MIN_GAMES_FOR_PERSONAL_WEIGHT, 1.0)
            score = (personal_win_rate * confidence) + (meta_win_rate * (1 - confidence))
        elif personal_win_rate is not None:
            score = personal_win_rate
        elif meta_win_rate is not None:
            score = meta_win_rate
        else:
            continue

        results.append({
            "champion": champion,
            "score": score,
            "personal_win_rate": personal_win_rate,
            "personal_games": personal_games,
            "meta_win_rate": meta_win_rate,
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results

async def get_duo_stats(discord_id_a: int, discord_id_b: int) -> dict | None:
    since = int(time.time()) - SECONDS_PER_WEEK
    matches = await get_duo_matches(discord_id_a, discord_id_b, since)

    if not matches:
        return None

    games = len(matches)
    wins = sum(m["win"] for m in matches)

    return {
        "games": games,
        "wins": wins,
        "win_rate": wins / games,
        "avg_kda_a": (sum(m["a_kills"] for m in matches) + sum(m["a_assists"] for m in matches)) / max(sum(m["a_deaths"] for m in matches), 1),
        "avg_kda_b": (sum(m["b_kills"] for m in matches) + sum(m["b_assists"] for m in matches)) / max(sum(m["b_deaths"] for m in matches), 1),
    }


async def build_leaderboard_embed(guild: discord.Guild, stat: str) -> discord.Embed:
    if stat == "honeyfruit":
        guild_wallets = await get_all_wallets(guild.id)
        guild_wallets.sort(key=lambda w: w["balance"], reverse=True)
        top_wallets = guild_wallets[:5]

        embed = discord.Embed(title="🏆 Leaderboard - Honeyfruit", color=discord.Color.gold())

        if not top_wallets:
            embed.description = "No one has any Honeyfruit, did we gamble too much or has no one bet yet?"
            return embed
        
        lines = [
            f"**{i+1}.** <@{w['discord_id']}> - {w['balance']:,} 🍯"
            for i, w in enumerate(top_wallets)
        ]
        embed.description = "\n".join(lines)
        return embed
    
    users = await get_registered_users_in_guild(guild)
    rows = []

    for user in users:
        label = f"{user['game_name']}#{user['tag_line']}"

        if stat == "rank":
            rank = await get_rank(user["discord_id"])
            if rank and rank["tier"]:
                rows.append((label, rank, _rank_sort_key(rank)))
        else:
            stats = await _weekly_stats_for_user(user["discord_id"])
            if stats:
                rows.append((label, stats, None))


    STAT_DISPLAY_NAMES = {
    "win_rate": "Win Rate",
    "kda": "KDA",
    "wins": "Total Wins",
    "rank": "Solo Queue Rank",
    "double_kills": "Double Kills",
    "triple_kills": "Triple Kills",
    "quadra_kills": "Quadra Kills",
    "penta_kills": "Penta Kills"
    }
    
    embed = discord.Embed(
        title=f"🏆 Leaderboard — {STAT_DISPLAY_NAMES.get(stat, stat.title())}",
        color=discord.Color.gold(),
    )

    if not rows:
        embed.description = "No data yet — play some games and run `/leaderboard` again after the next sync."
        return embed

    if stat == "rank":
        rows.sort(key=lambda r: r[2], reverse=True)
        lines = [
            f"**{i+1}.** {label} — {data['tier'].title()} {data['rank']} ({data['league_points']} LP)"
            for i, (label, data, _) in enumerate(rows)
        ]
    elif stat == "win_rate":
        rows.sort(key=lambda r: r[1]["win_rate"], reverse=True)
        lines = [
            f"**{i+1}.** {label} — {data['win_rate']*100:.0f}% ({data['wins']}/{data['games']})"
            for i, (label, data, _) in enumerate(rows)
        ]
    elif stat == "kda":
        rows.sort(key=lambda r: r[1]["avg_kda"], reverse=True)
        lines = [
            f"**{i+1}.** {label} — {data['avg_kda']:.2f} KDA ({data['games']} games)"
            for i, (label, data, _) in enumerate(rows)
        ]
    elif stat == "wins":
        rows.sort(key=lambda r: r[1]["wins"], reverse=True)
        lines = [
            f"**{i+1}.** {label} — {data['wins']} wins ({data['games']} games)"
            for i, (label, data, _) in enumerate(rows)
        ]
    elif stat == "double_kills":
        rows.sort(key=lambda r: r[1]["double_kills"], reverse=True)
        lines = [
            f"**{i+1}.** {label} — {data['double_kills']} Double Kill{'s' if data['double_kills'] != 1 else ''} ({data['games']} games)"
            for i, (label, data, _) in enumerate(rows)
        ]
    elif stat == "triple_kills":
        rows.sort(key=lambda r: r[1]["triple_kills"], reverse=True)
        lines = [
            f"**{i+1}.** {label} — {data['triple_kills']} Triple Kill{'s' if data['triple_kills'] != 1 else ''} ({data['games']} games)"
            for i, (label, data, _) in enumerate(rows)
        ]
    elif stat == "quadra_kills":
        rows.sort(key=lambda r: r[1]["quadra_kills"], reverse=True)
        lines = [
            f"**{i+1}.** {label} — {data['quadra_kills']} Quadra Kill{'s' if data['quadra_kills'] != 1 else ''} ({data['games']} games)"
            for i, (label, data, _) in enumerate(rows)
        ]
    elif stat == "penta_kills":
        rows.sort(key=lambda r: r[1]["penta_kills"], reverse=True)
        lines = [
            f"**{i+1}.** {label} — {data['penta_kills']} Penta Kill{'s' if data['penta_kills'] != 1 else ''} ({data['games']} games)"
            for i, (label, data, _) in enumerate(rows)
        ]
    else:
        lines = [f"Unknown stat: {stat}"]

    embed.description = "\n".join(lines)
    return embed

async def build_compare_embed(guild: discord.Guild, user_a: discord.Member, user_b: discord.Member) -> discord.Embed:
    record_a = await get_registered_user(user_a.id)
    record_b = await get_registered_user(user_b.id)

    embed = discord.Embed(title="⚔️ Head-to-Head — This Week", color=discord.Color.blurple())

    if not record_a or not record_b:
        missing = user_a.display_name if not record_a else user_b.display_name
        embed.description = f"{missing} hasn't registered yet — use `/register` first."
        return embed

    stats_a = await _weekly_stats_for_user(user_a.id)
    stats_b = await _weekly_stats_for_user(user_b.id)

    label_a = f"{record_a['game_name']}#{record_a['tag_line']}"
    label_b = f"{record_b['game_name']}#{record_b['tag_line']}"

    if not stats_a and not stats_b:
        embed.description = f"Neither {label_a} nor {label_b} has played this week."
        return embed

    def _format_stats(stats: dict | None) -> str:
        if not stats:
            return "No games played this week."
        return (
            f"Games: {stats['games']}\n"
            f"Wins: {stats['wins']}\n"
            f"Win Rate: {stats['win_rate']*100:.0f}%\n"
            f"Avg KDA: {stats['avg_kda']:.2f}\n"
            f"Double Kills: {stats['double_kills']}\n"
            f"Triple Kills: {stats['triple_kills']}\n"
            f"Quadra Kills: {stats['quadra_kills']}\n"
            f"Penta Kills: {stats['penta_kills']}"
        )

    embed.add_field(name=label_a, value=_format_stats(stats_a), inline=True)
    embed.add_field(name=label_b, value=_format_stats(stats_b), inline=True)

    return embed

async def get_top_honeyfruit_holder(guild_id: int) -> dict | None:
    wallets = await get_all_wallets(guild_id)
    if not wallets:
        return None
    return max(wallets, key=lambda w: w["balance"])

async def get_server_champion_stats(guild: discord.Guild, position: str) -> dict[str, dict]:
    # Returns {champion_name: {"wins": int, "losses": int, "games": int}} for
    # every champion played in the given position by members of this guild.
    # Used to show a server's own record alongside global OP.GG tier data.
    users = await get_registered_users_in_guild(guild)

    stats = defaultdict(lambda: {"wins": 0, "losses": 0, "games": 0})

    for user in users:
        matches = await get_recent_matches(user["discord_id"], 0)  # 0 = all-time
        for m in matches:
            if m["position"] != position:
                continue
            champion = m["champion"]
            stats[champion]["games"] += 1
            if m["win"]:
                stats[champion]["wins"] += 1
            else:
                stats[champion]["losses"] += 1

    return dict(stats)