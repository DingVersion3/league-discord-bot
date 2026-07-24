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
        if "team_id" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN team_id INTEGER DEFAULT 0")
        if "team_damage" not in existing_columns:
            await db.execute("ALTER TABLE matches ADD COLUMN team_damage INTEGER DEFAULT 0")
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

        await db.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                discord_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 1000
            )
        """)
        async with db.execute("PRAGMA table_info(wallets)") as cursor:
            existing_wallet_columns = {row[1] async for row in cursor}
        if existing_wallet_columns and "guild_id" not in existing_wallet_columns:
            await db.execute("ALTER TABLE wallets RENAME TO wallets_legacy")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                discord_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                balance INTEGER DEFAULT 1000,
                last_daily_claim INTEGER DEFAULT 0,
                PRIMARY KEY (discord_id, guild_id)
            )
        """)

        async with db.execute("PRAGMA table_info(bets)") as cursor:
            existing_bet_columns = {row[1] async for row in cursor}
        if existing_bet_columns and "guild_id" not in existing_bet_columns:
            await db.execute("ALTER TABLE bets RENAME TO bets_legacy")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                bet_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracked_discord_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                status TEXT DEFAULT 'open',
                opened_at INTEGER NOT NULL,
                resolved_at INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS wagers (
                bet_id INTEGER NOT NULL,
                bettor_discord_id INTEGER NOT NULL,
                prediction TEXT NOT NULL,
                amount INTEGER NOT NULL,
                PRIMARY KEY (bet_id, bettor_discord_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS dodgeball_games (
                game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                player_a INTEGER NOT NULL,
                player_b INTEGER NOT NULL,
                played_at INTEGER NOT NULL
            )
        """)
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
                      position: str = "", enemy_champion: str | None = None, team_id: int = 0, team_damage: int = 0) -> bool:
    async with _connect() as db:
        cursor = await db.execute(
            """
            INSERT INTO matches
                (match_id, discord_id, champion, win, kills, deaths, assists, damage, played_at, duration, cs, gold,
                doubleKills, tripleKills, quadraKills, pentaKills, position, enemy_champion, team_id, team_damage)
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            FROM users
            WHERE discord_id = ? AND puuid = ?
            ON CONFLICT(match_id, discord_id) DO NOTHING
            """,
            (match_id, discord_id, champion, int(win), kills, deaths, assists, damage, played_at, duration, cs, gold,
             doubleKills, tripleKills, quadraKills, pentaKills, position, enemy_champion, team_id, team_damage, discord_id, puuid),
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
        
async def get_duo_matches(discord_id_a: int, discord_id_b: int, since_timestamp: int) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT a.match_id, a.win, a.champion AS a_champion, a.kills AS a_kills,
                   a.deaths AS a_deaths, a.assists AS a_assists,
                   b.champion AS b_champion, b.kills AS b_kills,
                   b.deaths AS b_deaths, b.assists AS b_assists
            FROM matches a
            JOIN matches b ON a.match_id = b.match_id AND a.team_id = b.team_id
            WHERE a.discord_id = ? AND b.discord_id = ? AND a.played_at >= ?
            """,
            (discord_id_a, discord_id_b, since_timestamp),
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
    
async def get_wallet(discord_id: int, guild_id: int) -> int:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT balance FROM wallets WHERE discord_id = ? AND guild_id = ?",
            (discord_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return row["balance"]

        await db.execute(
            "INSERT INTO wallets (discord_id, guild_id, balance) VALUES (?, ?, 1000)",
            (discord_id, guild_id),
        )
        await db.commit()
        return 1000

async def get_all_wallets(guild_id: int) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM wallets WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def adjust_wallet(discord_id: int, guild_id: int, delta: int) -> int:
    await get_wallet(discord_id, guild_id)
    async with _connect() as db:
        await db.execute(
            "UPDATE wallets SET balance = balance + ? WHERE discord_id = ? AND guild_id = ?",
            (delta, discord_id, guild_id),
        )
        await db.commit()
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT balance FROM wallets WHERE discord_id = ? AND guild_id = ?",
            (discord_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row["balance"]

async def get_last_daily_claim(discord_id: int, guild_id: int) -> int:
    await get_wallet(discord_id, guild_id)
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT last_daily_claim FROM wallets WHERE discord_id = ? AND guild_id = ?",
            (discord_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row["last_daily_claim"] if row else 0

async def set_last_daily_claim(discord_id: int, guild_id: int, timestamp: int) -> None:
    async with _connect() as db:
        await db.execute(
            "UPDATE wallets SET last_daily_claim = ? WHERE discord_id = ? AND guild_id = ?",
            (timestamp, discord_id, guild_id),
        )
        await db.commit()


async def get_open_bet(tracked_discord_id: int, guild_id: int) -> dict | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM bets WHERE tracked_discord_id = ? AND guild_id = ? AND status = 'open'",
            (tracked_discord_id, guild_id),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_bet(tracked_discord_id: int, guild_id: int, opened_at: int) -> int:
    async with _connect() as db:
        cursor = await db.execute(
            "INSERT INTO bets (tracked_discord_id, guild_id, status, opened_at) VALUES (?, ?, 'open', ?)",
            (tracked_discord_id, guild_id, opened_at),
        )
        await db.commit()
        return cursor.lastrowid


async def place_wager(bet_id: int, bettor_discord_id: int, guild_id: int, prediction: str, amount: int) -> str | None:
    await get_wallet(bettor_discord_id, guild_id)

    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT amount FROM wagers WHERE bet_id = ? AND bettor_discord_id = ?",
            (bet_id, bettor_discord_id),
        ) as cursor:
            existing = await cursor.fetchone()

    if existing:
        await adjust_wallet(bettor_discord_id, guild_id, existing["amount"])

    balance = await get_wallet(bettor_discord_id, guild_id)
    if amount > balance:
        if existing:
            await adjust_wallet(bettor_discord_id, guild_id, -existing["amount"])
        return f"You only have {balance} Honeyfruit — can't wager {amount}."

    await adjust_wallet(bettor_discord_id, guild_id, -amount)

    async with _connect() as db:
        await db.execute(
            """
            INSERT INTO wagers (bet_id, bettor_discord_id, prediction, amount)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(bet_id, bettor_discord_id) DO UPDATE SET
                prediction = excluded.prediction,
                amount = excluded.amount
            """,
            (bet_id, bettor_discord_id, prediction, amount),
        )
        await db.commit()

    return None


async def get_wagers_for_bet(bet_id: int) -> list[dict]:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM wagers WHERE bet_id = ?", (bet_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def resolve_bet(bet_id: int, resolved_at: int) -> None:
    async with _connect() as db:
        await db.execute(
            "UPDATE bets SET status = 'resolved', resolved_at = ? WHERE bet_id = ?",
            (resolved_at, bet_id),
        )
        await db.commit()


async def migrate_legacy_wallets(guild_member_ids: dict[int, list[int]]) -> None:
    # guild_member_ids: {guild_id: [discord_id, discord_id, ...]} for every guild the bot is in.
    # For each legacy (pre-guild-scoping) wallet, credit the balance into every
    # server that user is currently a member of. Runs once; drops the legacy
    # table when done so it's a no-op on future startups.
    async with _connect() as db:
        async with db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='wallets_legacy'"
        ) as cursor:
            if not await cursor.fetchone():
                return

        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM wallets_legacy") as cursor:
            legacy_wallets = [dict(row) async for row in cursor]

        for wallet in legacy_wallets:
            discord_id = wallet["discord_id"]
            for guild_id, member_ids in guild_member_ids.items():
                if discord_id in member_ids:
                    await db.execute(
                        """
                        INSERT INTO wallets (discord_id, guild_id, balance, last_daily_claim)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(discord_id, guild_id) DO NOTHING
                        """,
                        (discord_id, guild_id, wallet["balance"], wallet.get("last_daily_claim", 0)),
                    )

        await db.execute("DROP TABLE wallets_legacy")
        await db.commit()

async def delete_user_data(discord_id: int) -> None:
    async with _connect() as db:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute("DELETE FROM matches WHERE discord_id = ?", (discord_id,))
        await db.execute("DELETE FROM ranks WHERE discord_id = ?", (discord_id,))
        await db.execute("DELETE FROM streaks WHERE discord_id = ?", (discord_id,))
        await db.execute("DELETE FROM wallets WHERE discord_id = ?", (discord_id,))
        await db.execute("DELETE FROM wagers WHERE bettor_discord_id = ?", (discord_id,))
        await db.execute("DELETE FROM bets WHERE tracked_discord_id = ?", (discord_id,))
        await db.execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
        await db.commit()

async def log_dodgeball_game(guild_id: int, player_a: int, player_b: int, played_at: int) -> None:
    async with _connect() as db:
        await db.execute(
            "INSERT INTO dodgeball_games (guild_id, player_a, player_b, played_at) VALUES (?, ?, ?, ?)",
            (guild_id, player_a, player_b, played_at),
        )
        await db.commit()


async def count_recent_dodgeball_games(guild_id: int, challenger_id: int, since_timestamp: int) -> int:
    async with _connect() as db:
        async with db.execute(
            """
            SELECT COUNT(*) FROM dodgeball_games
            WHERE guild_id = ? AND played_at >= ?
              AND (player_a = ? OR player_b = ?)
            """,
            (guild_id, since_timestamp, challenger_id, challenger_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def get_oldest_recent_dodgeball_game(guild_id: int, challenger_id: int, since_timestamp: int) -> int | None:
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT played_at FROM dodgeball_games
            WHERE guild_id = ? AND played_at >= ?
              AND (player_a = ? OR player_b = ?)
            ORDER BY played_at ASC
            LIMIT 1
            """,
            (guild_id, since_timestamp, challenger_id, challenger_id),
        ) as cursor:
            row = await cursor.fetchone()
            return row["played_at"] if row else None