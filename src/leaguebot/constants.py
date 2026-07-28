
# Shared constants used across multiple cogs/modules. Anything that's a pure
# config value, threshold, or timing setting lives here so it has one source
# of truth instead of being duplicated per-file.

# Deliberately NOT here: message/content templates (LOSS_MESSAGES, WIN_MESSAGES,
# STAT_SHARDS, REGION_CHOICES, etc.) since those are domain data specific to
# the file that uses them, not shared config. Also not here: DATA_DIR (depends
# on each file's own location on disk) and _SYNC_LOCK (a live runtime object,
# not a value).
import os
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()

# --- Time windows ---
SECONDS_PER_WEEK = 7 * 24 * 60 * 60
SECONDS_PER_DAY = 24 * 60 * 60

# --- Sync / polling ---
MATCHES_TO_CHECK = 100       # Riot's match-v5 caps count at 100
INTERVAL = 90                # alerts poll loop interval, in seconds
MIN_GAME_DURATION_SECONDS = 15 * 60  # below this, treat as a remake/early ff
MIN_GAMES_FOR_PERSONAL_WEIGHT = 3

# --- Alerts thresholds ---
STREAK_THRESHOLD = 5
MIN_GAMES_FOR_SPIKE = 5
SPIKE_THRESHOLD = 0.25

# --- Meme stats ---
MIN_GAMES_FOR_TITLES = 5

# --- Betting ---
DAILY_BONUS = 100
TRIVIA_REWARD = 100
MAX_TRIVIA_PER_DAY = 5

# --- Rank tiers ---
TIER_ORDER = [
    "IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM",
    "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER",
]
DIVISION_ORDER = {"IV": 0, "III": 1, "II": 2, "I": 3}
HIGH_TIERS = ("MASTER", "GRANDMASTER", "CHALLENGER")

# --- Riot API ---
API_KEY = os.getenv("RIOT_API_KEY")
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
PLATFORM_TO_REGIONAL = {
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas", "oc1": "americas",
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
    "kr": "asia", "jp1": "asia",
}

# --- Positions ---
POSITION_CHOICES = [
    {"name": "Top", "value": "TOP"},
    {"name": "Jungle", "value": "JUNGLE"},
    {"name": "Mid", "value": "MIDDLE"},
    {"name": "ADC", "value": "BOTTOM"},
    {"name": "Support", "value": "UTILITY"},
]
RIOT_TO_OPGG_POSITION = {
    "TOP": "top",
    "JUNGLE": "jungle",
    "MIDDLE": "mid",
    "BOTTOM": "adc",
    "UTILITY": "support",
}

CHAMPION_ALIASES = {
    "nunu": "Nunu & Willump",
    "willump": "Nunu & Willump",
    "jarvan": "Jarvan IV",
    "j4": "Jarvan IV",
    "mundo": "Dr. Mundo",
    "asol": "Aurelion Sol",
    "mf": "Miss Fortune",
    "tf": "Twisted Fate",
    "yi": "Master Yi",
    "blitz": "Blitzcrank",
    "morde": "Mordekaiser",
    "voli": "Volibear",
    "sera": "Seraphine",
    "kata": "Katarina",
    "cait": "Caitlyn",
    "ori": "Orianna",
    "malz": "Malzahar",
    "cass": "Cassiopeia",
    "gp": "Gangplank",
    "ww": "Warwick",
    "wu": "Wukong",
    "monkeyking": "Wukong",
    "trynd": "Tryndamere",
    "tryn": "Tryndamere",
    "panth": "Pantheon",
    "heca": "Hecarim",
    "eve": "Evelynn",
    "noc": "Nocturne",
    "sej": "Sejuani",
    "naut": "Nautilus",
    "lb": "LeBlanc",
    "ez": "Ezreal",
    "kog": "Kog'Maw",
    "khaz": "Kha'Zix",
    "rek": "Rek'Sai",
    "kass": "Kassadin",
    "ali": "Alistar",
    "xin": "Xin Zhao",
    "lee": "Lee Sin",
    "tk": "Tahm Kench",
    "tahm": "Tahm Kench",
    "renata": "Renata Glasc",
    "cho": "Cho'Gath",
    "mumu": "Amumu",
    "mao": "Maokai",
    "fiddle": "Fiddlesticks",
    "aphe": "Aphelios",
    "nid": "Nidalee",
    "shyv": "Shyvana",
    "trist": "Tristana",
    "raka": "Soraka",
}