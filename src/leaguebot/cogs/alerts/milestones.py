# Detects and messages round-number milestones: total games, wins, and losses
# tracked with ScuttleBuddy. Celebrates wins, roasts losses, in the same voice
# as the rest of the alert system.
import random

from leaguebot.db import get_bot_state, set_bot_state

MILESTONES = [1, 10, 25, 50, 100, 200, 300, 500, 750, 1000]
MILESTONE_STEP_AFTER_1000 = 500

GAME_MILESTONE_MESSAGES = [
    "That's {count} games tracked with ScuttleBuddy watching your every mistake. 🦀",
    "{count} games logged. ScuttleBuddy's seen things.",
]

WIN_MILESTONE_MESSAGES = [
    "🎉 {count} wins logged with ScuttleBuddy. Slightly less bad than before.",
    "{count} wins tracked. Someone tell Faker to watch his back.",
]

LOSS_MILESTONE_MESSAGES = [
    "💀 {count} losses tracked with ScuttleBuddy. Truly dedicated to the craft of losing.",
    "{count} losses logged. At this point it's not bad luck, it's a lifestyle.",
]

HIGH_GAME_MILESTONE_MESSAGES = [
    "Time for you and me you pop some champagne with {count} games logged.",
    "Just wanted to thank you for playing {count} games by your side.",
    "Not saying I'm a smoker, but you deserve a blunt after {count} games played.",
]

HIGH_WIN_MESSAGES = [
    "Is that Faker with his {count} win?",
    "Ain't no way you have {count} wins with me by your side!!!",
    "Do you have a life outside of League with {count} wins? Not trying to be mean, I love you cutie patootie.",
]

HIGH_LOSS_MESSAGES = [
    "It truly takes honor to have {count} losses.",
    "Oh my... {count} losses should've been a sign ages ago to try something else. You've got the passion of a Scuttlecrab.",
]


def _is_milestone(count: int) -> bool:
    if count in MILESTONES:
        return True
    if count > 1000 and count % MILESTONE_STEP_AFTER_1000 == 0:
        return True
    return False

def _is_high_milestone(count: int) -> bool:
    return _is_milestone(count) and count >= 100


async def get_milestone_message(discord_id: int, games: int, wins: int, losses: int) -> str | None:
    # Each counter tracks the last milestone it fired at, so a threshold only
    # alerts once. Without this, hitting 50 losses then winning would re-fire
    # the loss milestone -- losses didn't move, but the check runs again.
    
    for k, count, high_pool, norm_pool in (
        ("games", games, HIGH_GAME_MILESTONE_MESSAGES, GAME_MILESTONE_MESSAGES),
        ("wins", wins, HIGH_WIN_MESSAGES, WIN_MILESTONE_MESSAGES),
        ("losses", losses, HIGH_LOSS_MESSAGES, LOSS_MILESTONE_MESSAGES),
    ):
        if not _is_milestone(count):
            continue

        state_k = f"milestone:{discord_id}:{k}"
        if await get_bot_state(state_k) == str(count):
            continue

        await set_bot_state(state_k, str(count))
        pool = high_pool if _is_high_milestone(count) else norm_pool
        return random.choice(pool).format(count=count)

    return None