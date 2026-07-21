# Builds a legal, random League of Legends rune page from Data Dragon's
# runesReforged.json — i.e. respects the actual page-building rules
# (1 keystone + 3 minor runes in primary, 2 runes in secondary from
# different rows, 3 stat shards) rather than picking 4 fully random runes.


import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parents[4] / "data"

# Stat shards aren't in runesReforged.json — they're a fixed, separate system. Names only; we don't need exact Riot IDs for display purposes.
STAT_SHARDS = {
    "Offense": ["Adaptive Force", "Attack Speed", "Ability Haste"],
    "Flex": ["Adaptive Force", "Move Speed", "Health (Scaling)"],
    "Defense": ["Flat Health", "Tenacity", "Health (Scaling)"],
}

def load_trees() -> list[dict]:
    with open(DATA_DIR / "runes.json") as f:
        return json.load(f)
    
def build_random_page() -> dict:
    trees = load_trees()
    primary_tree, secondary_tree = random.sample(trees, 2)

    # Primary: slot 0 is the keystone row, slots 1-3 are minor rows
    keystone = random.choice(primary_tree["slots"][0]["runes"])
    minor_rows = primary_tree["slots"][1:]
    primary_runes = [random.choice(slot["runes"]) for slot in minor_rows]

    # Secondary: pick 2 different rows from slots 1-3 and pick one rune from the choosen rows
    secondary_rows = random.sample(secondary_tree["slots"][1:], 2)
    secondary_runes = [random.choice(slot["runes"]) for slot in secondary_rows]

    shards = {category: random.choice(options) for category, options in STAT_SHARDS.items()}

    return {
        "primary_tree": primary_tree["name"],
        "keystone": keystone["name"],
        "primary_runes": [r["name"] for r in primary_runes],
        "secondary_tree": secondary_tree["name"],
        "secondary_runes": [r["name"] for r in secondary_runes],
        "shards": shards,
    }