
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
SECONDS_PER_HOUR = 60 * 60

# --- Sync / polling ---
MATCHES_TO_CHECK = 100       # Riot's match-v5 caps count at 100
INTERVAL = 180                # alerts poll loop interval, in seconds
MIN_GAME_DURATION_SECONDS = 15 * 60  # below this, treat as a remake/early ff
MIN_GAMES_FOR_PERSONAL_WEIGHT = 3
TRACKED_GAME_MODES = ("CLASSIC", "ARAM") # Skip other modes to avoid data we don't want or data riot accidentally leaks out. 

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
BRACKETS = ["gold_plus", "emerald_plus", "diamond_plus", "all"]
DEFAULT_BRACKET = "gold_plus"
VALID_BRACKETS = {"gold_plus", "emerald_plus", "diamond_plus", "all"}

# --- Riot API ---
API_KEY = os.getenv("RIOT_API_KEY")
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)
PLATFORM_TO_REGIONAL = {
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas", "oc1": "americas",
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
    "kr": "asia", "jp1": "asia",
}

# --- Positions ---
# 5 different parameters for positions because everyone handles them differently, big sad :(
POSITIONS = [
    {"display": "Top",     "riot": "TOP",     "opgg": "top",     "opgg_response": "TOP"},
    {"display": "Jungle",  "riot": "JUNGLE",  "opgg": "jungle",  "opgg_response": "JUNGLE"},
    {"display": "Mid",     "riot": "MIDDLE",  "opgg": "mid",     "opgg_response": "MID"},
    {"display": "ADC",     "riot": "BOTTOM",  "opgg": "adc",     "opgg_response": "ADC"},
    {"display": "Support", "riot": "UTILITY", "opgg": "support", "opgg_response": "SUPPORT"},
]

POSITION_CHOICES = [{"name": p["display"], "value": p["riot"]} for p in POSITIONS]
RIOT_TO_OPGG_POSITION = {p["riot"]: p["opgg"] for p in POSITIONS}
OPGG_POSITIONS = [p["opgg"] for p in POSITIONS]
OPGG_POSITION_RESPONSE_NAMES = {p["opgg"]: p["opgg_response"] for p in POSITIONS}

# Champion/Position related Data
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

# To determine if we should be alerting for damage share, we need to know what type of support
# are playing and since that's not something defined anywhere, this list is what determines what
# champions are alerted for there damage share or not based on the style of support you are playing.
# Since this champions can technically cover multiple styles, this wont be supper accurate and will
# most definitely require monitoring and tinkering based on what the meta is for each particular champion.
# This is not an ideal way of handling this but unsure of how else to handle it.
SUPPORT_CHAMPION_STYLE = {
    "Damage": {
        "Brand",
        "Zyra",
        "Lux",
        "Xerath",
        "Velkoz",
        "Hwei",
        "Swain",
        "Seraphine",
        "Pyke",
        "Morgana",
        "Senna",
        "Mel",
        "Zilean",
        "Neeko",
        "Orianna",
        "Taliyah",
        "Anivia",
        "Veigar",
        "Fiddlesticks",
        "Ashe",
        "Heimerdinger",
        "Shaco",
        "Karthus",
        "Teemo",
        "Twitch",
        "Zoe",
    },
    "Engage": {
        "Nautilus",
        "Leona",
        "Blitzcrank",
        "Braum",
        "Tahm Kench",
        "Thresh",
        "Maokai",
        "Rell",
        "Poppy",
        "Pantheon",
        "Rakan",
        "Alistar",
        "Camille",
        "Shen",
        "Gragas",
        "Amumu",
        "Galio",
        "Sett",
        "Sion",
        "K'Sante",
        "Zac",
        "Malphite",
        "Jarvan",
        "Kled",
        "Sejuani",
    },
    "Enchanters": {
        "Milio",
        "Nami",
        "Lulu",
        "Karma",
        "Janna",
        "Sona",
        "Yuumi",
        "Soraka",
        "Renata Glasc",
        "Bard",
        "Ivern",
        "Taric",
    },
}

# Performance thresholds per rank bracket, per role, per stat.
# Each stat has a "bad" and "good" cutoff: at or below "bad" scores 0,
# at or above "good" scores 100, and anything between scales linearly.
#
# All rate stats are per-minute so they're comparable across game lengths.
# KDA is (kills + assists) / max(deaths, 1) for supports, and
# (kills + assists * ASSIST_WEIGHT) / max(deaths, 1) for every other role,
# since assists inflate support KDA by design.
PERFORMANCE_THRESHOLDS = {
    "gold_plus": {
        "TOP": {
            "kda":            {"bad": 1.8, "good": 2.8},
            "cs_per_min":     {"bad": 5.0, "good": 7.0},
            "damage_share":   {"bad": 0.17, "good": 0.25},
            "gold_per_min":   {"bad": 340.0, "good": 425.0},
            "vision_per_min": {"bad": 0.3, "good": 0.8},
        },
        "JUNGLE": {
            "kda":            {"bad": 2.0, "good": 3.2},
            "cs_per_min":     {"bad": 4.8, "good": 6.5},
            "damage_share":   {"bad": 0.11, "good": 0.18},
            "gold_per_min":   {"bad": 310.0, "good": 390.0},
            "vision_per_min": {"bad": 0.5, "good": 1.0},
        },
        "MIDDLE": {
            "kda":            {"bad": 1.9, "good": 3.0},
            "cs_per_min":     {"bad": 5.0, "good": 7.2},
            "damage_share":   {"bad": 0.22, "good": 0.32},
            "gold_per_min":   {"bad": 360.0, "good": 460.0},
            "vision_per_min": {"bad": 0.5, "good": 1.0},
        },
        "BOTTOM": {
            "kda":            {"bad": 1.8, "good": 3.0},
            "cs_per_min":     {"bad": 5.0, "good": 7.2},
            "damage_share":   {"bad": 0.19, "good": 0.32},
            "gold_per_min":   {"bad": 370.0, "good": 500.0},
            "vision_per_min": {"bad": 0.3, "good": 0.8},
        },
        "UTILITY": {
            "kda":            {"bad": 2.0, "good": 3.5},
            "cs_per_min":     {"bad": 0.0, "good": 0.5},
            "damage_share":   {"bad": 0.1, "good": 0.2},
            "gold_per_min":   {"bad": 240.0, "good": 350.0},
            "vision_per_min": {"bad": 1.0, "good": 2.3},
        },
    },
    "emerald_plus": {
        "TOP": {
            "kda":            {"bad": 2.0, "good": 3.2},
            "cs_per_min":     {"bad": 6.0, "good": 8.0},
            "damage_share":   {"bad": 0.17, "good": 0.28},
            "gold_per_min":   {"bad": 380.0, "good": 500.0},
            "vision_per_min": {"bad": 0.3, "good": 0.8},
        },
        "JUNGLE": {
            "kda":            {"bad": 2.0, "good": 4.0},
            "cs_per_min":     {"bad": 4.8, "good": 7.7},
            "damage_share":   {"bad": 0.12, "good": 0.25},
            "gold_per_min":   {"bad": 340.0, "good": 465.0},
            "vision_per_min": {"bad": 0.6, "good": 1.65},
        },
        "MIDDLE": {
            "kda":            {"bad": 2.0, "good": 3.9},
            "cs_per_min":     {"bad": 6.2, "good": 8.5},
            "damage_share":   {"bad": 0.24, "good": 0.37},
            "gold_per_min":   {"bad": 390.0, "good": 525.0},
            "vision_per_min": {"bad": 0.5, "good": 1.2},
        },
        "BOTTOM": {
            "kda":            {"bad": 2.1, "good": 4.1},
            "cs_per_min":     {"bad": 6.5, "good": 9.3},
            "damage_share":   {"bad": 0.20, "good": 0.35},
            "gold_per_min":   {"bad": 390.0, "good": 540.0},
            "vision_per_min": {"bad": 0.4, "good": 0.9},
        },
        "UTILITY": {
            "kda":            {"bad": 2.2, "good": 3.8},
            "cs_per_min":     {"bad": 0.3, "good": 0.9},
            "damage_share":   {"bad": 0.12, "good": 0.28},
            "gold_per_min":   {"bad": 260.0, "good": 400.0},
            "vision_per_min": {"bad": 1.5, "good": 2.8},
        },
    },
    "diamond_plus": {
        "TOP": {
            "kda":            {"bad": 2.2, "good": 3.7},
            "cs_per_min":     {"bad": 6.8, "good": 8.9},
            "damage_share":   {"bad": 0.2, "good": 0.3},
            "gold_per_min":   {"bad": 390.0, "good": 480.0},
            "vision_per_min": {"bad": 0.4, "good": 0.8},
        },
        "JUNGLE": {
            "kda":            {"bad": 2.4, "good": 4.0},
            "cs_per_min":     {"bad": 5.5, "good": 6.8},
            "damage_share":   {"bad": 0.13, "good": 0.28},
            "gold_per_min":   {"bad": 360.0, "good": 450.0},
            "vision_per_min": {"bad": 0.7, "good": 1.5},
        },
        "MIDDLE": {
            "kda":            {"bad": 2.4, "good": 4.0},
            "cs_per_min":     {"bad": 7.0, "good": 9.5},
            "damage_share":   {"bad": 0.24, "good": 0.38},
            "gold_per_min":   {"bad": 410.0, "good": 535.0},
            "vision_per_min": {"bad": 0.5, "good": 1.2},
        },
        "BOTTOM": {
            "kda":            {"bad": 2.5, "good": 4.2},
            "cs_per_min":     {"bad": 8.0, "good": 9.9},
            "damage_share":   {"bad": 0.20, "good": 0.35},
            "gold_per_min":   {"bad": 430.0, "good": 560.0},
            "vision_per_min": {"bad": 0.4, "good": 0.9},
        },
        "UTILITY": {
            "kda":            {"bad": 2.8, "good": 5.2},
            "cs_per_min":     {"bad": 0.5, "good": 1.5},
            "damage_share":   {"bad": 0.12, "good": 0.26},
            "gold_per_min":   {"bad": 260.0, "good": 380.0},
            "vision_per_min": {"bad": 1.8, "good": 3.2},
        },
    }, 
    "all": {
        "TOP": {
            "kda":            {"bad": 1.8, "good": 2.8},
            "cs_per_min":     {"bad": 4.8, "good": 8.5},
            "damage_share":   {"bad": 0.18, "good": 0.26},
            "gold_per_min":   {"bad": 340.0, "good": 455.0},
            "vision_per_min": {"bad": 0.4, "good": 1.2},
        },
        "JUNGLE": {
            "kda":            {"bad": 1.9, "good": 3.8},
            "cs_per_min":     {"bad": 4.2, "good": 7.5},
            "damage_share":   {"bad": 0.12, "good": 0.2},
            "gold_per_min":   {"bad": 310.0, "good": 470.0},
            "vision_per_min": {"bad": 0.7, "good": 2.2},
        },
        "MIDDLE": {
            "kda":            {"bad": 1.8, "good": 3.7},
            "cs_per_min":     {"bad": 5.0, "good": 8.4},
            "damage_share":   {"bad": 0.22, "good": 0.32},
            "gold_per_min":   {"bad": 350.0, "good": 510.0},
            "vision_per_min": {"bad": 0.5, "good": 1.0},
        },
        "BOTTOM": {
            "kda":            {"bad": 2.2, "good": 3.5},
            "cs_per_min":     {"bad": 5.8, "good": 9.2},
            "damage_share":   {"bad": 0.20, "good": 0.35},
            "gold_per_min":   {"bad": 390.0, "good": 510.0},
            "vision_per_min": {"bad": 0.4, "good": 0.8},
        },
        "UTILITY": {
            "kda":            {"bad": 2.8, "good": 4.5},
            "cs_per_min":     {"bad": 0.5, "good": 1.8},
            "damage_share":   {"bad": 0.12, "good": 0.22},
            "gold_per_min":   {"bad": 240.0, "good": 360.0},
            "vision_per_min": {"bad": 1.5, "good": 2.8},
        },
    },
}

# How much an assist counts toward KDA for non-support roles.
ASSIST_WEIGHT = 0.5

# Relative weight of each stat in the final performance score. Sums to 1.0 per role.
PERFORMANCE_WEIGHTS = {
    "TOP":     {"kda": 0.25, "cs_per_min": 0.25, "damage_share": 0.25, "gold_per_min": 0.15, "vision_per_min": 0.10},
    "JUNGLE":  {"kda": 0.25, "cs_per_min": 0.20, "damage_share": 0.25, "gold_per_min": 0.15, "vision_per_min": 0.15},
    "MIDDLE":  {"kda": 0.25, "cs_per_min": 0.25, "damage_share": 0.25, "gold_per_min": 0.15, "vision_per_min": 0.10},
    "BOTTOM":  {"kda": 0.25, "cs_per_min": 0.25, "damage_share": 0.25, "gold_per_min": 0.20, "vision_per_min": 0.05},
    "UTILITY": {"kda": 0.30, "cs_per_min": 0.05, "damage_share": 0.15, "gold_per_min": 0.10, "vision_per_min": 0.40},
}

# Maps a player's tier to which threshold bracket to score them against.
TIER_TO_BRACKET = {
    "IRON": "gold_plus",
    "BRONZE": "gold_plus",
    "SILVER": "gold_plus",
    "GOLD": "gold_plus",
    "PLATINUM": "emerald_plus",
    "EMERALD": "emerald_plus",
    "DIAMOND": "diamond_plus",
    "MASTER": "diamond_plus",
    "GRANDMASTER": "diamond_plus",
    "CHALLENGER": "diamond_plus",
}
DEFAULT_PERFORMANCE_BRACKET = "all"