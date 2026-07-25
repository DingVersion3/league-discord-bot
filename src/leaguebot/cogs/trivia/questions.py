# Builds a single random trivia question: either "guess the champion from
# this quote" or "guess the champion from this ability name/icon."
import json
import random
from pathlib import Path

from leaguebot.cogs.memestats.wisdom import CHAMPION_QUOTES

DATA_DIR = Path(__file__).parents[4] / "data"


def _load_champions() -> dict[str, str]:
    with open(DATA_DIR / "champions.json") as f:
        return json.load(f)["champions"]


def _load_abilities() -> tuple[str, dict]:
    with open(DATA_DIR / "abilities.json") as f:
        data = json.load(f)
        return data["version"], data["abilities"]


def _build_choices(correct_name: str, all_names: list[str]) -> list[str]:
    wrong_pool = [n for n in all_names if n != correct_name]
    wrong_choices = random.sample(wrong_pool, 3)
    choices = wrong_choices + [correct_name]
    random.shuffle(choices)
    return choices


def generate_quote_question() -> dict:
    champions = _load_champions()
    champion_name, quote = random.choice(CHAMPION_QUOTES)

    return {
        "type": "quote",
        "prompt": f"Which champion said this?\n\n*\"{quote}\"*",
        "image_url": None,
        "correct": champion_name,
        "choices": _build_choices(champion_name, list(champions.values())),
    }


def generate_ability_question() -> dict:
    champions = _load_champions()
    version, abilities = _load_abilities()

    champ_id = random.choice(list(abilities.keys()))
    ability = random.choice(abilities[champ_id])
    champion_name = champions[champ_id]

    folder = "passive" if ability["slot"] == "P" else "spell"
    icon_url = f"https://ddragon.leagueoflegends.com/cdn/{version}/img/{folder}/{ability['icon']}"

    return {
        "type": "ability",
        "prompt": f"Which champion has the ability **{ability['name']}**?",
        "image_url": icon_url,
        "correct": champion_name,
        "choices": _build_choices(champion_name, list(champions.values())),
    }


def generate_question() -> dict:
    generator = random.choice([generate_quote_question, generate_ability_question])
    return generator()