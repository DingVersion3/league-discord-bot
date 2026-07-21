
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
MATCHES_TO_CHECK = 15       # how many recent match IDs to pull per user, per sync
INTERVAL = 90                # alerts poll loop interval, in seconds
MIN_GAME_DURATION_SECONDS = 15 * 60  # below this, treat as a remake/early ff

# --- Alerts thresholds ---
STREAK_THRESHOLD = 5
MIN_GAMES_FOR_SPIKE = 5
SPIKE_THRESHOLD = 0.25

# --- Meme stats ---
MIN_GAMES_FOR_TITLES = 5

# --- Betting ---
DAILY_BONUS = 100

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