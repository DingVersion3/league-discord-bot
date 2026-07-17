# ScuttleBuddy

A League of Legends companion bot for Discord — post-game recaps, weekly leaderboards, random champion/rune rolls, and weekly meme stats for your server.

## Features

- **`/register`** — Link your Discord account to your Riot ID and select your region
- **`/lastgame [user] [riot_id]`** — Detailed recap of the most recent match: KDA, CS, gold, damage, full item build, and role quest item (e.g. lane-quest boots). Works for any registered server member or a raw Riot ID.
- **`/leaderboard [stat]`** — Server leaderboard ranked by win rate, average KDA, total wins, or current Solo Queue rank
- **`/randomchamp`** — Random champion with a fully legal random rune page (correct keystone/row rules) and splash art
- **`/memestats`** — Weekly superlatives: most deaths, best KDA game, longest game, most damage, most gold, most CS
- **`/setleaderboardchannel`** — Configure where the weekly leaderboard + meme stats auto-post
- **`/streaks [user]`** - Checks for win/lose streaks for user inserted/defaults to user who puts in command
- **`/compare [user1] [user2]`** - Compares users stats for the week.
- **`/syncnow`** — Manually trigger the weekly data sync + post (admin only)

- Every Monday, the bot automatically syncs fresh match/rank data for all registered users and posts the leaderboard (all four stat categories) plus meme stats to the configured channel.
- ScuttleBuddy will send alerts for win/loss streaks(in intervals of 5) and when you and/or your friends rank up or rank down(from silver to gold, master to grandmaster)

## Setup

https://discord.com/oauth2/authorize?client_id=1524695530444427314 is the link to add the bot to your discord server.


## Tech stack

- Python 3.11+, `discord.py` (slash commands via `app_commands`)
- Riot Games API (`account-v1`, `match-v5`, `league-v4`) for live match/rank data
- Riot Data Dragon CDN for static champion/rune/item data
- SQLite (`aiosqlite`) for caching registered users, weekly match history, and rank snapshots

## Known limitations

- Riot development API keys expire every 24 hours and must be manually regenerated at [developer.riotgames.com](https://developer.riotgames.com) — a production key would remove this, but requires Riot's app approval process.
