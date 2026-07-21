# ScuttleBuddy

A League of Legends companion bot for Discord — post-game recaps, weekly leaderboards, random champion/rune rolls, and weekly meme stats for your server.

## Features

- **`/register`** — Link your Discord account to your Riot ID and select your region
- **`/lastgame [user] [riot_id]`** — Detailed recap of the most recent match: KDA, CS, gold, damage, full item build, and role quest item (e.g. lane-quest boots). Works for any registered server member or a raw Riot ID.
- **`/leaderboard [stat]`** — Server leaderboard ranked by win rate, average KDA, total wins, current Solo Queue rank, double, triple, quadra, pentakills and Honeyfruit
- **`/randomchamp`** — Random champion with a fully legal random rune page (correct keystone/row rules) and splash art
- **`/memestats`** — Weekly superlatives: most deaths, best KDA game, longest game, most damage, most gold, most CS
- **`/setleaderboardchannel`** — Configure where the weekly leaderboard + meme stats auto-post
- **`/streak [user]`** - Checks for win/lose streaks for user inserted/defaults to user who puts in command
- **`/compare [user1] [user2]`** - Compares users stats for the week.
- **`/nemesis [user1]`** - Shows you the champion you lost to the most in the lane you played the most
- **`/teamcomp [players] [team_a] [team_b] [randomize_runes]`** - Generates a random position/champion assignment for a group of players Can define who is on each team or let it randomize it.(amount of users is optional but 2 is the minimum)
- **`/duo [user1] [user2]`** — Win rate/KDA for user games played together
- **`/whoshouldiplay [optional champion list]`** - Takes your champion winrate data and suggests who you play. Optionally you can add a list of champs youd like to play and have it filtered by those champs
- **`/openbet`** — Open betting on your own next game (Honeyfruit, a fake in-server currency)
- **`/bet [player] [prediction] [amount]`** — Wager Honeyfruit on whether a player's open bet will resolve as a win or loss
- **`/honeyfruit [user]`** — Check your (or someone else's) Honeyfruit balance
- **`/dailybonus`** - Collect 100 Honeyfruit every 24 hours
- **`/profile`** - Shows you a players profile card
- **`/help`** - Lists every ScuttleBuddy command, grouped by category
- **`/syncnow`** — Manually trigger the weekly data sync + post (admin only)

- Every Monday, the bot automatically syncs fresh match/rank data for all registered users and posts the leaderboard (all four stat categories) plus meme stats to the configured channel.
- ScuttleBuddy will send alerts for win/loss streaks(in intervals of 5) and when you and/or your friends rank up or rank down(from silver to gold, master to grandmaster)
- ScuttleBuddy will also send alerts for good/bad games for certain stats(cs, damage etc.), and is based off of the players averages for those stats, not predefined by rank like most companion apps would be

## In Progress Features

- **`Bet/predicition system`** - server members bet on outcomes of games before a players game starts(either manually started by user or automatically started when the game starts via API calls). Bets are made in the currency of Honeyfruit(fake currency that is not tied to anything real, you probably wont be purchasing McDonalds with your Honeyfruit...)
- **`Postgame spike detector`** - flag when someone had a really good or bad game/stat(KDA, CS/M compared to the role/rank average, etc)
- **POTENTIAL FEATURE** **`Champion pool suggestions`** based on what's strong into the enemy comp (look into doing algorithmic processing for champ counters via match-v5 API). Doing this is saying im going to basically make a web app but it runs inside discord so im unsure if thats the direction im after with this project or not. If im able to parse from data that is high elo per say and use thoses as baseline counters to things then maybe its a sophisticated enough system to bring a twist to the party. dont commit this message to github or youll ruin your idea(maybe youre a nobody after all :p )

## Setup

https://discord.com/oauth2/authorize?client_id=1524695530444427314 is the link to add the bot to your discord server.


## Tech stack

- Python 3.11+, `discord.py` (slash commands via `app_commands`)
- Riot Games API (`account-v1`, `match-v5`, `league-v4`) for live match/rank data
- Riot Data Dragon CDN for static champion/rune/item data
- SQLite (`aiosqlite`) for caching registered users, weekly match history, and rank snapshots
- Supports multiple regions (`NA`, `EUW`, `EUNE`, `KR`, `JP`, `BR`, `LAN`, `LAS`, `OCE`, `TR`, `RU`)


## Known limitations

- Riot development API keys expire every 24 hours and must be manually regenerated at [developer.riotgames.com](https://developer.riotgames.com) — a production key would remove this, but requires Riot's app approval process.
- Match data growth unbounded.
- Regional routing accuracy depends on user input since /register requires the user to self-select their region. theres no validation that the region matches their actual Riot account.
