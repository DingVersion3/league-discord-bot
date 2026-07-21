# Pulls a player's most recent match and generates a roast or compliment
# about one randomly-chosen stat from that game, for on-demand /roast use.
import random

from leaguebot.db import get_recent_matches

ROAST_TEMPLATES = {
    "kda": [
        "{kda:.1f} KDA on {champion}? That's a participation trophy stat line.",
        "Went {kills}/{deaths}/{assists} on {champion}. The enemy team thanks you for your service.",
    ],
    "deaths": [
        "{deaths} deaths on {champion}. Did you donate your soul to the enemy jungler?",
        "{deaths} deaths — at some point that's not feeding, that's a subscription service.",
    ],
    "cs": [
        "{cs_per_min:.1f} CS/min on {champion}. The minions filed a missing persons report.",
        "{cs} CS in {duration_min}m on {champion}? Were you AFK farming excuses instead?",
    ],
    "damage_share": [
        "{damage_share:.0f}% damage share on {champion}. You brought a butter knife to a gunfight.",
        "Only {damage_share:.0f}% of the team's damage on {champion} — decorative pick, truly.",
    ],
}

COMPLIMENT_TEMPLATES = {
    "kda": [
        "{kda:.1f} KDA on {champion}?! Absolute menace, the enemy team should apologize.",
        "{kills}/{deaths}/{assists} on {champion} — that's a highlight reel right there.",
    ],
    "deaths": [
        "Only {deaths} death(s) on {champion}. Untouchable.",
        "{deaths} death(s) the whole game on {champion}? Built different.",
    ],
    "cs": [
        "{cs_per_min:.1f} CS/min on {champion} — the lane opponent never stood a chance.",
        "{cs} CS in {duration_min}m on {champion}. Farming machine.",
    ],
    "damage_share": [
        "{damage_share:.0f}% damage share on {champion}. You basically soloed that game.",
        "Carrying {damage_share:.0f}% of the team's damage on {champion} — actual main character energy.",
    ],
}


async def get_latest_match(discord_id: int) -> dict | None:
    matches = await get_recent_matches(discord_id, 0)  # 0 = all-time
    if not matches:
        return None
    return max(matches, key=lambda m: m["played_at"])


def generate_line(match: dict, mode: str) -> str:
    kills, deaths, assists = match["kills"], match["deaths"], match["assists"]
    kda = (kills + assists) / max(deaths, 1)
    duration_min = max(match["duration"] // 60, 1)
    cs_per_min = match["cs"] / duration_min

    categories = ["kda", "deaths"]
    if match["position"] != "UTILITY":
        categories.append("cs")
    if match.get("team_damage", 0) > 0:
        categories.append("damage_share")

    category = random.choice(categories)
    templates = ROAST_TEMPLATES if mode == "roast" else COMPLIMENT_TEMPLATES

    template = random.choice(templates[category])
    return template.format(
        champion=match["champion"],
        kills=kills, deaths=deaths, assists=assists, kda=kda,
        cs=match["cs"], cs_per_min=cs_per_min, duration_min=duration_min,
        damage_share=(match["damage"] / max(match.get("team_damage", 1), 1)) * 100,
    )