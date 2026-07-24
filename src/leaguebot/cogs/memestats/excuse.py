# /excuse: a random self-directed excuse for a bad game. Always available, no match data needed.
import random

EXCUSES = [
    "My mouse disconnected. Twice. Both times mid-teamfight.",
    "The jungler never ganked. Not once. I checked.",
    "It was ping issues, I swear.",
    "My cat walked across the keyboard during the final fight.",
    "I was one-tricking a new champion, don't judge me.",
    "The enemy team just... didn't misplay. Unfair, honestly.",
    "My internet provider chose that exact moment to do 'maintenance.'",
    "I got distracted by a Discord notification. It was important. Probably.",
    "The Rift Herald personally sabotaged me.",
    "I was testing a new build. On purpose. In ranked. Yes.",
    "My little brother unplugged the router.",
    "Riot's servers hate me specifically.",
    "I was playing with my off-hand as a personal challenge.",
    "The enemy jungler was clearly scripting. There's no other explanation.",
]


def get_excuse() -> str:
    return random.choice(EXCUSES)