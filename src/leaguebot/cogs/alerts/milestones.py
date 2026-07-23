# Detects and messages round-number milestones: total games, wins, and losses
# tracked with ScuttleBuddy. Celebrates wins, roasts losses, in the same voice
# as the rest of the alert system.
import random

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
    "Not saying I'm a smoker, but you deserve a blunt after {count} games.",
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


def get_milestone_message(games: int, wins: int, losses: int) -> str | None:
    # Checks all three counters; returns the first milestone hit, if any.
    # (In the rare case a game triggers two counters — e.g. games + wins —
    # only one message is sent to avoid spamming the channel.)
    if _is_high_milestone(games):
        return random.choice(HIGH_GAME_MILESTONE_MESSAGES).format(count=games)
    elif _is_milestone(games):
        return random.choice(GAME_MILESTONE_MESSAGES).format(count=games)
    if _is_high_milestone(wins):
        return random.choice(HIGH_WIN_MESSAGES).format(count=wins)
    elif _is_milestone(wins):
        return random.choice(WIN_MILESTONE_MESSAGES).format(count=wins)
    if _is_high_milestone(losses):
        return random.choice(HIGH_LOSS_MESSAGES).format(count=losses)
    elif _is_milestone(losses):
        return random.choice(LOSS_MILESTONE_MESSAGES).format(count=losses)
    return None