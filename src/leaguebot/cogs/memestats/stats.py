# Builds a weekly meme stats embed: fun superlatives pulled from every registered user's matches this week (most deaths, longest game, etc).
import time

import discord

from collections import defaultdict
from leaguebot.db import get_all_recent_matches
from leaguebot.constants import SECONDS_PER_WEEK, MIN_GAMES_FOR_TITLES


def _label(match: dict) -> str:
    return f"{match['game_name']}#{match['tag_line']}"


async def build_meme_stats_embed(guild: discord.Guild) -> discord.Embed:
    since = int(time.time()) - SECONDS_PER_WEEK
    all_matches = await get_all_recent_matches(since)
    matches = [m for m in all_matches if guild.get_member(m["discord_id"]) is not None]

    embed = discord.Embed(title="🎭 Weekly Meme Stats", color=discord.Color.purple())

    if not matches:
        embed.description = "No games played this week — get out of here!"
        return embed

    most_deaths = max(matches, key=lambda m: m["deaths"])
    embed.add_field(
        name="💀 Most Deaths",
        value=f"{_label(most_deaths)} — {most_deaths['deaths']} deaths on {most_deaths['champion']}",
        inline=False,
    )

    best_kda = max(matches, key=lambda m: (m["kills"] + m["assists"]) / max(m["deaths"], 1))
    kda_ratio = (best_kda["kills"] + best_kda["assists"]) / max(best_kda["deaths"], 1)
    embed.add_field(
        name="⭐ Best KDA Game",
        value=f"{_label(best_kda)} — {best_kda['kills']}/{best_kda['deaths']}/{best_kda['assists']} "
              f"({kda_ratio:.1f} KDA) on {best_kda['champion']}",
        inline=False,
    )

    biggest_carry = max(matches, key=lambda m: m["damage"])
    embed.add_field(
        name="🗡️ Most Damage Dealt",
        value=f"{_label(biggest_carry)} — {biggest_carry['damage']:,} damage on {biggest_carry['champion']}",
        inline=False,
    )

    richest = max(matches, key=lambda m: m["gold"])
    embed.add_field(
        name="💰 Most Gold Earned",
        value=f"{_label(richest)} — {richest['gold']:,} gold on {richest['champion']}",
        inline=False,
    )

    hardest_farmer = max(matches, key=lambda m: m["cs"])
    embed.add_field(
        name="🌾 Most CS",
        value=f"{_label(hardest_farmer)} — {hardest_farmer['cs']} CS on {hardest_farmer['champion']}",
        inline=False,
    )

    worst_kda = min(matches, key=lambda m: (m["kills"] + m["assists"]) / max(m["deaths"], 1))
    worst_kda_ratio = (worst_kda["kills"] + worst_kda["assists"]) / max(worst_kda["deaths"], 1)
    embed.add_field(
        name="🍗 Inter of the Week",
        value=f"{_label(worst_kda)} - {worst_kda['kills']}/{worst_kda['deaths']}/{worst_kda['assists']}"
              f"({worst_kda_ratio:.1f} KDA) on {worst_kda['champion']}",
        inline=False,
    )

    longest_game = max(matches, key=lambda m: m["duration"])
    embed.add_field(
        name="⏱️ The Marathon Runner",
        value=f"{_label(longest_game)} — {longest_game['duration'] // 60}m on {longest_game['champion']}",
        inline=False,
    )

    # group weekly matches by user, then check for champion data
    matches_by_user = defaultdict(list)
    for m in matches:
        matches_by_user[m["discord_id"]].append(m)

    one_trick_label = None
    one_trick_champ = None
    one_trick_pct = 0

    denny_label = None
    denny_champ_count = 0

    for discord_id, user_matches in  matches_by_user.items():
        if len(user_matches) < MIN_GAMES_FOR_TITLES:
            continue

        champ_counts = defaultdict(int)
        for m in user_matches:
            champ_counts[m["champion"]] += 1

        top_champ, top_count = max(champ_counts.items(), key=lambda c: c[1])
        pct_on_top_champ = top_count / len(user_matches)

        # highest % of games on a single champion(60% to qualify)
        if pct_on_top_champ >= 0.6 and pct_on_top_champ > one_trick_pct:
            one_trick_pct = pct_on_top_champ
            one_trick_champ = top_champ
            one_trick_label = _label(user_matches[0])

        #dennys menu: most distinct champs played
        distinct_champs  = len(champ_counts)
        if distinct_champs > denny_champ_count:
            denny_champ_count = distinct_champs
            denny_label = _label(user_matches[0])

    if one_trick_label:
        embed.add_field(
            name="🎯 One Trick",
            value=f"{one_trick_label} — {one_trick_pct*100:.0f}% of games on {one_trick_champ}",
            inline=False,
        )

    if denny_label:
        embed.add_field(
            name="📖 Menu at Denny's",
            value=f"{denny_label} — {denny_champ_count} different champions played",
            inline=False,
        )

    #kadeem: most losses in the week

    kadeem_label = None
    kadeem_loses = 0

    for discord_id, user_matches in matches_by_user.items():
        if len(user_matches) < MIN_GAMES_FOR_TITLES:
            continue
        losses = sum(1 for m in user_matches if not m["win"])
        if losses > kadeem_loses:
            kadeem_loses = losses
            kadeem_label = _label(user_matches[0])

    if kadeem_label and kadeem_loses > 0:
        embed.add_field(
            name="🐝 Kadeem",
            value=f"{kadeem_label} — {kadeem_loses} losses this week and still queued up",
            inline=False,
        )

    # Speenrun any % - shortest loss
    losing_games = [m for m in matches if not m["win"]]
    if losing_games:
        fastest_loss = min(losing_games, key=lambda m: m["duration"])
        embed.add_field(
            name="🏃 Speedrun Any%",
            value=f"{_label(fastest_loss)} - lost in {fastest_loss['duration'] // 60}m on {fastest_loss['champion']}",
            inline=False,
        )

    # Got Carried: worst kda in winning match
    winning_games = [m for m in matches if m["win"]]
    if winning_games:
        carried = min(winning_games, key=lambda m: (m["kills"] + m["assists"]) / max(m["deaths"], 1))
        carried_kda = (carried["kills"] + carried["assists"]) / max(carried["deaths"], 1)
        embed.add_field(
            name="🛞 Got Carried",
            value=f"{_label(carried)} — won with a {carried_kda:.1f} KDA ({carried['kills']}/{carried['deaths']}/{carried['assists']}) on {carried['champion']}",
            inline=False,
        )

    # Luxury Canon Minion: worst damage-per-gold, among above-median gold earners
    gold_values = sorted(m["gold"] for m in matches if m["gold"] > 0)
    if gold_values:
        median_gold = gold_values[len(gold_values) // 2]
        big_spenders = [m for m in matches if m["gold"] >= median_gold and m["gold"] > 0]
        if big_spenders:
            lux_minion = min(big_spenders, key=lambda m: m["damage"] / m["gold"])
            embed.add_field(
                name="💸 Luxury Cannon Minion",
                value=f"{_label(lux_minion)} - {lux_minion['gold']:,} gold spent for only {lux_minion['damage']:,} damage on {lux_minion['champion']}",
                inline=False,
            )

    # Glass cannon: top 3 in damage and deaths in the same game
    top_damage_ids = {id(m) for m in sorted(matches, key=lambda m: m["damage"], reverse=True)[:3]}
    top_deaths_ids = {id(m) for m in sorted(matches, key=lambda m: m["deaths"], reverse=True)[:3]}
    glass_cannon_candidates = [m for m in matches if id(m) in top_damage_ids and id(m) in top_deaths_ids]
    if glass_cannon_candidates:
        glass_cannon = glass_cannon_candidates[0]
        embed.add_field(
            name="💎 Glass Cannon",
            value=f"{_label(glass_cannon)} — {glass_cannon['damage']:,} damage AND {glass_cannon['deaths']} deaths on {glass_cannon['champion']}",
            inline=False,
        )
    embed.set_footer(text=f"Based on {len(matches)} game(s) played this week")
    return embed