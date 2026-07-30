"""
Fetches the latest champion and rune data from Riot's Data Dragon CDN
and caches it locally in data/. Re-run this after each League patch.

Usage: python -m leaguebot.fetch_ddragon
"""
import json
import time
import urllib.request
from pathlib import Path

from leaguebot.helpers import log

# data/ lives at the project root, four levels up from this file
DATA_DIR = Path(__file__).parents[2] / "data"
DATA_DIR.mkdir(exist_ok=True)


def fetch_json(url: str) -> dict | list:
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    log("Fetching latest patch version...")
    versions = fetch_json("https://ddragon.leagueoflegends.com/api/versions.json")
    latest = versions[0]
    log(f"Latest version: {latest}")

    log("Fetching champion data...")
    champ_data = fetch_json(
        f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json"
    )
    champions = {
        champ_id: champ_info["name"]
        for champ_id, champ_info in sorted(champ_data["data"].items())
    }
    with open(DATA_DIR / "champions.json", "w") as f:
        json.dump({"version": latest, "champions": champions}, f, indent=2)
    log(f"Saved {len(champions)} champions to data/champions.json")

    log("Fetching rune data...")
    rune_data = fetch_json(
        f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/runesReforged.json"
    )
    with open(DATA_DIR / "runes.json", "w") as f:
        json.dump(rune_data, f, indent=2)
    log("Saved rune trees to data/runes.json")

    log("Fetching item data...")
    item_data = fetch_json(
        f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/item.json"
    )
    items = {item_id: info["name"] for item_id, info in item_data["data"].items()}
    with open(DATA_DIR / "items.json", "w") as f:
        json.dump({"version": latest, "items": items}, f, indent=2)
    log(f"Saved {len(items)} items to data/items.json")

    log(f"Fetching individual ability data for {len(champions)} champions (this takes a bit)...")
    abilities = {}
    for champ_id in champions:
        detail = fetch_json(
            f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion/{champ_id}.json"
        )
        champ_detail = detail["data"][champ_id]
        entries = [{
            "slot": "P",
            "name": champ_detail["passive"]["name"],
            "icon": champ_detail["passive"]["image"]["full"],
        }]
        for slot, spell in zip(["Q", "W", "E", "R"], champ_detail["spells"]):
            entries.append({"slot": slot, "name": spell["name"], "icon": spell["image"]["full"]})
        abilities[champ_id] = entries
        time.sleep(0.05)  # light throttling to be polite to Data Dragon's CDN

    with open(DATA_DIR / "abilities.json", "w") as f:
        json.dump({"version": latest, "abilities": abilities}, f, indent=2)
    log(f"Saved ability data for {len(abilities)} champions to data/abilities.json")


if __name__ == "__main__":
    main()