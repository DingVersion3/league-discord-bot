#Shared Riot API client. Handles account lookup and match history/details via match-v5 and account-v1, both under regional routing.
from urllib.parse import quote

import aiohttp
import asyncio

from leaguebot.constants import REQUEST_TIMEOUT, API_KEY


class RiotAPIError(Exception):
    # Raised when the Riot API returns a non-2xx response.
    def __init__(self, status: int | None, message: str):
        self.status = status
        self.message = message
        super().__init__(f"Riot API error {status}: {message}")


async def _get(session: aiohttp.ClientSession, url: str, max_retries: int = 3) -> dict | list:
    if not API_KEY:
        raise RiotAPIError(None, "Riot API is unavailable.")

    headers = {"X-Riot-Token": API_KEY}

    for attempt in range(max_retries + 1):
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status in (401, 403):
                    raise RiotAPIError(
                        resp.status,
                        "API key rejected — dev keys expire every 24h, regenerate at "
                        "https://developer.riotgames.com and update .env",
                    )
                if resp.status == 404:
                    raise RiotAPIError(404, "Riot account or match not found.")
                if resp.status == 429:
                    if attempt >= max_retries:
                        raise RiotAPIError(429, "Riot API rate limit reached; try again later.")
                    # Riot tells us exactly how long to wait.
                    retry_after = int(resp.headers.get("Retry-After", 10))
                    print(f"[RIOT] rate limited, waiting {retry_after}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_after)
                    continue
                if resp.status != 200:
                    raise RiotAPIError(resp.status, "Riot API request failed; try again later.")
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            raise RiotAPIError(None, "Riot API request failed; try again later.") from error

    raise RiotAPIError(429, "Riot API rate limit reached; try again later.")


async def get_puuid(game_name: str, tag_line: str, regional_route: str = "americas") -> str:
    # Look up a player's PUUID from their Riot ID (e.g. 'ammumu', 'NA1').
    url = (
        f"https://{regional_route}.api.riotgames.com/riot/account/v1/accounts"
        f"/by-riot-id/{quote(game_name, safe='')}/{quote(tag_line, safe='')}"
    )
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        data = await _get(session, url)
        return data["puuid"]


async def get_match_ids(puuid: str, regional_route: str = "americas", count: int = 1) -> list[str]:
    # Get the most recent match IDs for a player, newest first.
    url = (
        f"https://{regional_route}.api.riotgames.com/lol/match/v5/matches"
        f"/by-puuid/{puuid}/ids?start=0&count={count}"
    )
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        return await _get(session, url)


async def get_match(match_id: str, regional_route: str = "americas") -> dict:
    # Get full match details by match ID.
    url = f"https://{regional_route}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        return await _get(session, url)


async def get_rank(puuid: str, platform_route: str = "na1") -> dict | None:
    #Get a player's current Ranked Solo/Duo standing. Returns None if unranked (no RANKED_SOLO_5x5 entry).
    url = f"https://{platform_route}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        entries = await _get(session, url)
        for entry in entries:
            if entry["queueType"] == "RANKED_SOLO_5x5":
                return {
                    "tier": entry["tier"],
                    "rank": entry["rank"],
                    "league_points": entry["leaguePoints"],
                    "wins": entry["wins"],
                    "losses": entry["losses"],
                }
        return None