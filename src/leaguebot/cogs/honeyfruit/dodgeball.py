# Mundo Dodgeball: a 3-round wagered mini-game. Each round, one player throws
# and the other either gets hit or dodges. Most hits after 3 rounds wins the pot.
import random
import time

from leaguebot.db import log_dodgeball_game, count_recent_dodgeball_games, get_oldest_recent_dodgeball_game
from leaguebot.constants import SECONDS_PER_DAY

MAX_GAMES_PER_24H = 3

HIT_MESSAGES = [
    "{thrower} hurls an Infected Bonesaw — it slows and slams right into {target}!",
    "{thrower} winds up and lands the bonesaw square in {target}'s chest!",
    "{target} never saw it coming — {thrower}'s bonesaw connects clean!",
]

MISS_MESSAGES = [
    "{thrower} throws wild — the bonesaw sails past {target} entirely!",
    "{target} dodges gracefully as {thrower}'s bonesaw clatters harmlessly to the ground!",
    "{thrower} whiffs completely. {target} didn't even flinch.",
]


async def can_play(guild_id: int, challenger_id: int) -> tuple[bool, int | None]:
    # Returns (can_play, seconds_until_next_available). seconds is None if can_play is True.
    since = int(time.time()) - SECONDS_PER_DAY
    count = await count_recent_dodgeball_games(guild_id, challenger_id, since)

    if count < MAX_GAMES_PER_24H:
        return True, None

    oldest_game_time = await get_oldest_recent_dodgeball_game(guild_id, challenger_id, since)
    if oldest_game_time is None:
        return True, None  # shouldn't happen, but fail open rather than block incorrectly

    seconds_until_available = (oldest_game_time + SECONDS_PER_DAY) - int(time.time())
    return False, max(seconds_until_available, 0)


def _play_round(name_a: str, name_b: str) -> tuple[str, str | None]:
    thrower, target = random.sample([name_a, name_b], 2)
    hit = random.random() < 0.5
    template = random.choice(HIT_MESSAGES if hit else MISS_MESSAGES)
    return template.format(thrower=thrower, target=target), (thrower if hit else None)


async def play_match(guild_id: int, id_a: int, name_a: str, id_b: int, name_b: str) -> dict:
    rounds = []
    hits = {name_a: 0, name_b: 0}

    for _ in range(3):
        line, winner_name = _play_round(name_a, name_b)
        rounds.append(line)
        if winner_name:
            hits[winner_name] += 1

    if hits[name_a] > hits[name_b]:
        winner_id = id_a
    elif hits[name_b] > hits[name_a]:
        winner_id = id_b
    else:
        winner_id = None  # tie

    await log_dodgeball_game(guild_id, id_a, id_b, int(time.time()))
    return {"rounds": rounds, "hits": hits, "winner_id": winner_id}