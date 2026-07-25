import aiohttp

from leaguebot.db import get_bot_state, set_bot_state, get_leaderboard_channel

PATCH_STATE_KEY = "last_known_patch_version"


async def _fetch_latest_version() -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get("https://ddragon.leagueoflegends.com/api/versions.json") as resp:
            versions = await resp.json()
            return versions[0]


def _build_patch_url(version: str) -> str:
    major, minor, *_ = version.split(".")
    return f"https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-{major}-{minor}-notes/"


async def check_for_new_patch(bot) -> None:
    latest_version = await _fetch_latest_version()
    last_seen = await get_bot_state(PATCH_STATE_KEY)

    if last_seen is None:
        await set_bot_state(PATCH_STATE_KEY, latest_version)
        return

    if latest_version == last_seen:
        return

    await set_bot_state(PATCH_STATE_KEY, latest_version)

    major, minor, *_ = latest_version.split(".")
    patch_url = _build_patch_url(latest_version)
    message = f"🦀 **Patch {major}.{minor} is live!**\n\n📋 Read the full patch notes: {patch_url}"

    for guild in bot.guilds:
        channel_id = await get_leaderboard_channel(guild.id)
        if not channel_id:
            continue
        channel = guild.get_channel(channel_id)
        if channel:
            await channel.send(message)