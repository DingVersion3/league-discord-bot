import random
from leaguebot.db import update_streak, get_streak, set_last_alert_streak
from leaguebot.constants import TIER_ORDER, STREAK_THRESHOLD, MIN_GAMES_FOR_SPIKE, SPIKE_THRESHOLD, HIGH_TIERS

LOSS_MESSAGES = [
    "Maybe you should quit while you're ahead...",
    "Can't end on a loss, but maybe you should make an exception after {streak} losses...",
    "You're on a {streak}-game losing streak... maybe get off for the day 🤷",
    "After {streak} losses in a row, you might want to go touch some grass, or find a girlfriend or both",
    "You might need to change your underwear after this {streak} loss streak... it smells",
]

WIN_MESSAGES = [
    "{streak}-game win streak? Maybe time for a shower or food break.",
    "{streak} in a row? Whos letting you win?",
    "you must be Iron with {streak} wins in a row...",
    "Ain't no way you won {streak} in a row!",
    "Is that Faker? Only Faker could win {streak} in a row!",
    "Damn not even https://dpm.lol/NOTJT-6767 could win {streak} in a row",
]

RANK_UP_MESSAGES = [
    "climbed from {old} to {new} 📈",
    "ranked up! {old} → {new}",
]

RANK_DOWN_MESSAGES = [
    "just fell from {old} to {new} 📉",
    "demoted: {old} → {new}. rough.",
]

MASTER_PLUS_MESSAGE = "just hit {new}!! 🏆"

def tier_index(tier: str | None) -> int:
    if not tier or tier not in TIER_ORDER:
        return -1
    return TIER_ORDER.index(tier)

def display_tier(tier: str, rank: str | None) -> str:
    if tier in HIGH_TIERS:
        return tier.title()
    return f"{tier.title()} {rank}"

def get_rank_change_message(old_rank: dict | None, new_rank: dict | None):
    # returns an alert message if the tier changed(ignore division changes)
    old_tier = old_rank["tier"] if old_rank else None
    new_tier = new_rank["tier"]

    if old_tier is None:
        return None # first rank seen for the user. baseline, dont alert
    
    old_idx = tier_index(old_tier)
    new_idx = tier_index(new_tier)

    if old_idx == new_idx:
        return None # same tier, divison only change(silver 4 to silver 3, etc)
    
    old_display = display_tier(old_tier, old_rank.get("rank"))
    new_display = display_tier(new_tier, new_rank.get("rank"))

    if new_idx > old_idx:
        if new_tier in HIGH_TIERS and old_tier not in HIGH_TIERS:
            return MASTER_PLUS_MESSAGE.format(new=new_display)
        return random.choice(RANK_UP_MESSAGES).format(old=old_display, new=new_display)
    else:
        return random.choice(RANK_DOWN_MESSAGES).format(old=old_display, new=new_display)

async def process_result(discord_id: int, won: bool) -> str | None:
    # updates the streak and returns an alert message when the threshold is newly crossed
    # hits a multiple of streak threshold(5,10,15,20,...)
    current_streak, streak_type = await update_streak(discord_id, won)

    if current_streak < STREAK_THRESHOLD or current_streak % STREAK_THRESHOLD != 0:
        return None
    
    row = await get_streak(discord_id)
    last_alert = row["last_alert_streak"] if row else 0
    if current_streak == last_alert:
        return None
    
    await set_last_alert_streak(discord_id, current_streak)

    template = random.choice(LOSS_MESSAGES if streak_type == "loss" else WIN_MESSAGES)
    return template.format(streak=current_streak)

def get_spike_message(new_match: dict, previous_matches: list[dict]) -> str | None:
    if len(previous_matches) < MIN_GAMES_FOR_SPIKE:
        return None
    
    spikes = []
    is_support = new_match.get("position") == "UTILITY"
    is_classic = new_match.get("game_mode") == "CLASSIC"

    if not is_support and is_classic:
        new_cs_per_min = new_match["cs"] / max(new_match["duration"] / 60, 1)
        avg_cs_per_min = sum(m["cs"] / max(m["duration"] / 60, 1) for m in previous_matches) / len(previous_matches)

        if avg_cs_per_min > 0:
            cs_delta = (new_cs_per_min - avg_cs_per_min) / avg_cs_per_min
            if cs_delta >= SPIKE_THRESHOLD:
                spikes.append(f"CS was way up — {new_cs_per_min:.1f}/min vs your usual {avg_cs_per_min:.1f}/min 📈")
            elif cs_delta <= -SPIKE_THRESHOLD:
                spikes.append(f"CS took a hit — {new_cs_per_min:.1f}/min vs your usual {avg_cs_per_min:.1f}/min 📉")

    new_damage_share = new_match["damage"] / max(new_match["team_damage"], 1)
    avg_damage_share = sum(m["damage"] / max(m["team_damage"], 1) for m in previous_matches if m["team_damage"] > 0) / max(
        len([m for m in previous_matches if m["team_damage"] > 0]), 1
    )


    if avg_damage_share > 0:
        dmg_delta = (new_damage_share - avg_damage_share) / avg_damage_share
        if dmg_delta >= SPIKE_THRESHOLD:
            spikes.append(f"Damage share spiked — {new_damage_share*100:.0f}% of team damage vs your usual {avg_damage_share*100:.0f}% 💥")
        elif dmg_delta <= -SPIKE_THRESHOLD:
            spikes.append(f"Damage share dropped — {new_damage_share*100:.0f}% of team damage vs your usual {avg_damage_share*100:.0f}% 🫥")

    if not spikes:
        return None

    return " | ".join(spikes)