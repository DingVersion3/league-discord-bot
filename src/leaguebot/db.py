# SQLite-backed storage for Discord user -> Riot account mappings. Used by /register and any command that accepts @user instead of a raw Riot ID.
import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "bot.db"


async def init_db() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                discord_id INTEGER PRIMARY KEY,
                game_name TEXT NOT NULL,
                tag_line TEXT NOT NULL,
                puuid TEXT NOT NULL
            )
        """)
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
        await db.commit()


async def register_user(discord_id: int, game_name: str, tag_line: str, puuid: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (discord_id, game_name, tag_line, puuid)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                game_name = excluded.game_name,
                tag_line = excluded.tag_line,
                puuid = excluded.puuid
            """,
            (discord_id, game_name, tag_line, puuid),
        )
        await db.commit()


async def get_registered_user(discord_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None
        
async def get_all_registered_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def save_match(discord_id: int, match_id: str, champion: str, win: bool,
                      kills: int, deaths: int, assists: int, damage: int, played_at: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO matches
                (match_id, discord_id, champion, win, kills, deaths, assists, damage, played_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (match_id, discord_id, champion, int(win), kills, deaths, assists, damage, played_at),
        )
        await db.commit()


async def get_recent_matches(discord_id: int, since_timestamp: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM matches WHERE discord_id = ? AND played_at >= ?",
            (discord_id, since_timestamp),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def save_rank(discord_id: int, tier: str | None, rank: str | None,
                     league_points: int | None, updated_at: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO ranks (discord_id, tier, rank, league_points, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                tier = excluded.tier,
                rank = excluded.rank,
                league_points = excluded.league_points,
                updated_at = excluded.updated_at
            """,
            (discord_id, tier, rank, league_points, updated_at),
        )
        await db.commit()


async def get_rank(discord_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM ranks WHERE discord_id = ?", (discord_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def set_leaderboard_channel(guild_id: int, channel_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT leaderboard_channel_id FROM settings WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row["leaderboard_channel_id"] if row else None