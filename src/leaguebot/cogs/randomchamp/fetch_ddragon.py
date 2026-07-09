"""
Fetches the latest champion and rune data from Riot's Data Dragon CDN
and caches it locally in data/. Re-run this after each League patch.

Usage: python -m leaguebot.cogs.randomchamp.fetch_ddragon
"""
import json
import urllib.request
from pathlib import Path

# data/ lives at the project root, four levels up from this file
DATA_DIR = Path(__file__).parents[4] / "data"
DATA_DIR.mkdir(exist_ok=True)


def fetch_json(url: str) -> dict | list:
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    print("Fetching latest patch version...")
    versions = fetch_json("https://ddragon.leagueoflegends.com/api/versions.json")
    latest = versions[0]
    print(f"Latest version: {latest}")

    print("Fetching champion data...")
    champ_data = fetch_json(
        f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/champion.json"
    )
    champions = {
        champ_id: champ_info["name"]
        for champ_id, champ_info in sorted(champ_data["data"].items())
    }
    with open(DATA_DIR / "champions.json", "w") as f:
        json.dump({"version": latest, "champions": champions}, f, indent=2)
    print(f"Saved {len(champions)} champions to data/champions.json")

    print("Fetching rune data...")
    rune_data = fetch_json(
        f"https://ddragon.leagueoflegends.com/cdn/{latest}/data/en_US/runesReforged.json"
    )
    with open(DATA_DIR / "runes.json", "w") as f:
        json.dump(rune_data, f, indent=2)
    print("Saved rune trees to data/runes.json")


if __name__ == "__main__":
    main()