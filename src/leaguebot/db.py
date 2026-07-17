# SQLite-backed storage for Discord user -> Riot account mappings. Used by /register and any command that accepts @user instead of a raw Riot ID.
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
import discord

DB_PATH = Path(__file__).parent.parent.parent / "data" / "bot.db"


@asynccontextmanager
async def _connect():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA busy_timeout = 5000")
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.touch(mode=0o600, exist_ok=True)
    DB_PATH.chmod(0o600)

    async with _connect() as db:
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                discord_id INTEGER PRIMARY KEY,
                game_name TEXT NOT NULL,
                tag_line TEXT NOT NULL,
                puuid TEXT NOT NULL
            )
        """)
        async with db.execute("PRAGMA table_info(users)") as cursor:
            existing_user_columns = {row[1] async for row in cursor}
        if "regional_route" not in existing_user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN regional_route TEXT DEFAULT 'americas'")
        if "platform_route" not in existing_user_columns:
            await db.execute("ALTER TABLE users ADD COLUMN platform_route TEXT DEFAULT 'na1'")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT NOT NULL,
                discord_id INTEGER NOT NULL,
                champion TEXT NOT NULL,
                win INTEGER NOT NULL,
                kills INTEGER NOT NULL,
                deaths INTEGER NOT NULL,
                assists INTEGER NOT NULL,
                damage INTEGER NOT NULL,
                played_at INTEGER NOT NULL,
                PRIMARY KEY (match_id, discord_id)
            )
        """)
        async with db.execute("PRAGMA table_info(matches)") as cursor:
            existing_columns = {row[1] async for row in cursor}
        if "duration" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN duration INTEGER DEFAULT 0")
        if "cs" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN cs INTEGER DEFAULT 0")
        if "gold" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN gold INTEGER DEFAULT 0")
        if "doubleKills" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN doubleKills INTEGER DEFAULT 0")
        if "tripleKills" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN tripleKills INTEGER DEFAULT 0")
        if "quadraKills" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN quadraKills INTEGER DEFAULT 0")
        if "pentaKills" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN pentaKills INTEGER DEFAULT 0")
        if "position" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN position TEXT DEFAULT ''")
        if "enemy_champion" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN enemy_champion TEXT DEFAULT ''")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ranks (
                discord_id INTEGER PRIMARY KEY,
                tier TEXT,
                rank TEXT,
                league_points INTEGER,
                updated_at INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                leaderboard_channel_id INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS streaks (
                discord_id INTEGER PRIMARY KEY,
                current_streak INTEGER DEFAULT 0,
                streak_type TEXT DEFAULT 'none',
                last_alert_streak INTEGER DEFAULT 0
            )
        """)
        async with db.execute("PRAGMA table_info(streaks)") as cursor:
            existing_streak_columns = {row[1] async for row in cursor}
        if "last_match_id" not in existing_streak_columns:
            await db.execute("ALTER TABLE streaks ADD COLUMN last_match_id TEXT")
        await db.commit()

async def register_user(discord_id: int, game_name: str, tag_line: str, puuid: str, regional_route: str = "americas", platform_route: str = "na1") -> None:
    async with _connect() as db:
        await db.execute("BEGIN IMMEDIATE")
        stale_profile = (discord_id, discord_id, puuid)
        for table in ("matches", "ranks", "streaks"):
            await db.execute(
                f"""
                DELETE FROM {table}
                WHERE discord_id = ?
                  AND EXISTS (
                      SELECT 1 FROM users
                      WHERE discord_id = ? AND puuid <> ?
                  )
                """,
                stale_profile,
            )
        await db.execute(
            """
            INSERT INTO users (discord_id, game_name, tag_line, puuid, regional_route, platform_route)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                game_name = excluded.game_name,
                tag_line = excluded.tag_line,
                puuid = excluded.puuid,
                regional_route = excluded.regional_route,
                platform_route = excluded.platform_route
            """,
            (discord_id, game_name, tag_line, puuid, regional_route, platform_route),
        )
        await db.commit()


async def get_registered_user(discord_id: int) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
        
async def get_all_registered_users() -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        
async def get_registered_users_in_guild(guild: discord.Guild) -> list[dict]:
    all_users = await get_all_registered_users()
    return [u for u in all_users if guild.get_member(u["discord_id"]) is not None]


async def save_match(discord_id: int, puuid: str, match_id: str, champion: str, win: bool,
                      kills: int, deaths: int, assists: int, damage: int, played_at: int,
                      duration: int = 0, cs: int = 0, gold: int = 0, doubleKills: int = 0,
                      tripleKills: int = 0, quadraKills: int = 0, pentaKills: int = 0,
                      position: str = "", enemy_champion: str | None = None) -> bool:
    async with _connect() as db:
        cursor = await db.execute(
            """
            INSERT INTO matches
                (match_id, discord_id, champion, win, kills, deaths, assists, damage, played_at, duration, cs, gold,
                doubleKills, tripleKills, quadraKills, pentaKills, position, enemy_champion)
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            FROM users
            WHERE discord_id = ? AND puuid = ?
            ON CONFLICT(match_id, discord_id) DO NOTHING
            """,
            (match_id, discord_id, champion, int(win), kills, deaths, assists, damage, played_at, duration, cs, gold,
             doubleKills, tripleKills, quadraKills, pentaKills, position, enemy_champion, discord_id, puuid),
        )
        await db.commit()
        return cursor.rowcount == 1


async def get_recent_matches(discord_id: int, since_timestamp: int) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM matches WHERE discord_id = ? AND played_at >= ?",
            (discord_id, since_timestamp),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        
async def get_all_recent_matches(since_timestamp: int) -> list[dict]:
    # All matches (across every registered user) played since the given timestamp, joined with the player's Riot ID for display purposes.
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT matches.*, users.game_name, users.tag_line
            FROM matches
            JOIN users ON matches.discord_id = users.discord_id
            WHERE matches.played_at >= ?
            """,
            (since_timestamp,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def save_rank(discord_id: int, puuid: str, tier: str | None, rank: str | None,
                     league_points: int | None, updated_at: int) -> bool:
    async with _connect() as db:
        cursor = await db.execute(
            """
            INSERT INTO ranks (discord_id, tier, rank, league_points, updated_at)
            SELECT ?, ?, ?, ?, ?
            FROM users
            WHERE discord_id = ? AND puuid = ?
            ON CONFLICT(discord_id) DO UPDATE SET
                tier = excluded.tier,
                rank = excluded.rank,
                league_points = excluded.league_points,
                updated_at = excluded.updated_at
            """,
            (discord_id, tier, rank, league_points, updated_at, discord_id, puuid),
        )
        await db.commit()
        return cursor.rowcount == 1


async def get_rank(discord_id: int) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ranks WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def set_leaderboard_channel(guild_id: int, channel_id: int) -> None:
    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO settings (guild_id, leaderboard_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET leaderboard_channel_id = excluded.leaderboard_channel_id
            """,
            (guild_id, channel_id),
        )
        await db.commit()


async def get_leaderboard_channel(guild_id: int) -> int | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT leaderboard_channel_id FROM settings WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["leaderboard_channel_id"] if row else None
        
async def get_streak(discord_id: int) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM streaks WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
        
async def update_streak(discord_id: int, won: bool) -> tuple[int, str]:
    # Returns (current streak, streak type(W/L)) after applying the result
    result_type = "win" if won else "loss"
    existing = await get_streak(discord_id)
    if existing is None:
        current_streak = 1
    elif existing["streak_type"] == result_type:
        current_streak = existing["current_streak"] + 1
    else:
        current_streak = 1

    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO streaks (discord_id, current_streak, streak_type)
            VALUES (?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                current_streak = excluded.current_streak,
                streak_type = excluded.streak_type
            """,
            (discord_id, current_streak, result_type),
        )
        await db.commit()
    return current_streak, result_type

async def set_last_alert_streak(discord_id: int, streak: int) -> None:
    async with _connect() as db:
        await db.execute(
            "UPDATE streaks SET last_alert_streak = ? WHERE discord_id = ?",
            (streak, discord_id),
        )
        await db.commit()

async def set_last_match_id(discord_id: int, match_id: str) -> None:
    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO streaks (discord_id, last_match_id)
            VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET last_match_id = excluded.last_match_id
            """,
            (discord_id, match_id),
        )
        await db.commit()
