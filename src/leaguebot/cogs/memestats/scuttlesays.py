import random

RESPONSES = [
    "Yes.",
    "No",
    "Absolutely not.",
    "The crab has spoken: yes.",
    "Ask again after you buy wards.",
    "Signs point to yes, but so did your last 5 games and look how that went.",
    "No. Just... no.",
    "The river knows all. The river says no.",
    "Yes, but you'll regret it.",
    "Scuttle says maybe. Scuttle also says stop asking a crab for life advice.",
    "It is decidedly so.",
    "Outlook not so good.",
    "Very doubtful.",
    "Without a doubt, yes.",
]

def get_response() -> str:
    return random.choice(RESPONSES)