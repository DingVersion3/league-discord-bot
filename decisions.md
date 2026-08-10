# ScuttleBuddy — Architecture & Decisions

This document explains what ScuttleBuddy is, how it's put together, and *why*
each significant decision was made. The README covers what the commands do;
this covers the reasoning behind them, the tradeoffs accepted, and the known
limitations that aren't obvious from reading the code.

Written so that future-you (or anyone else) can pick this up months later
without having to re-derive why things are the way they are.

---

## 1. What This Is

ScuttleBuddy is a League of Legends Discord bot for a small friend group. It
tracks match history, posts weekly leaderboards and joke superlatives, fires
live alerts on streaks and rank changes, runs a fake-currency betting economy,
and pulls meta/matchup data from OP.GG.

It runs on a VPS under PM2, backed by SQLite, and is deployed via `git pull`.

**Scale it was built for:** Small scale across a small amount of Discord servers.
Several decisions below only make sense at that scale and would need revisiting
if it grew.

---

## 2. Project Structure

```
src/leaguebot/
├── bot.py                    # entrypoint, cog loading, on_ready, error handler
├── db.py                     # ALL SQL. every table, every query
├── constants.py              # shared config values
├── riot_api.py               # Riot API client
├── opgg_client.py            # OP.GG MCP client + tier list cache reader
├── items.py                  # item ID -> name lookup
├── helpers.py                # helper functions across the project
├── fetch_ddragon.py          # manual: caches champion/rune/item/ability data
├── fetch_opgg_tierlist.py    # manual: caches OP.GG tier data (~1 hour per rank bracket you pull)
├── repuuid.py                # manual: re-resolves every registered user's PUUID under the current API key(used when changing from test to personal key, etc.)
└── cogs/
    ├── admin/                # /setleaderboardchannel, /syncnow, scheduled tasks
    ├── alerts/               # /streak + the live poll loop
    ├── betting/              # Honeyfruit economy, dodgeball
    ├── core/                 # /help, /profile, /status
    ├── leaderboard/          # /leaderboard, /compare, /nemesis, /duo + sync
    ├── memestats/            # /memestats, /roast, /wisdom, /excuse, /scuttlesays
    ├── opgg/                 # /matchup, /tierlist
    ├── randomchamp/          # /randomchamp, /teamcomp
    ├── recap/                # /register, /unregister, /lastgame, /whoshouldiplay
    └── trivia/               # /trivia
```

### Why cogs are folders, not single files

Each cog folder holds `cog.py` (the Discord-facing commands) plus separate
modules for the actual logic. `cog.py` stays thin — it handles interactions,
builds embeds, and calls out to logic modules that know nothing about Discord.

This means the logic is testable without a Discord connection, and reading
`cog.py` tells you what a feature *does* without wading through how it computes
things.

### Why some files live at the root instead of in a cog

The test used repeatedly: **would this file exist if its feature didn't?**

- `db.py`, `constants.py`, `riot_api.py`, `opgg_client.py` — survive any single
  feature being deleted. Root level.
- `sync.py` (in `leaderboard/`) — exists to populate leaderboard data. Admin
  triggers it, but that doesn't make it shared infrastructure.
- `poll.py` (in `alerts/`) — exists to detect matches for alerts. It also saves
  matches, but that's a side effect of already having the data in hand.
- `fetch_ddragon.py` — originally lived in `randomchamp/`, moved to root once
  `trivia/` also depended on its output. It was never really randomchamp's file;
  it populates shared data.

Vague structural unease isn't a good enough reason to move things. The signal
worth acting on is when a change becomes annoying to make because of where a
file lives.

---

## 3. Data Layer

### All SQL lives in `db.py`

Cogs never open a database connection. They call named functions like
`get_recent_matches(discord_id, since)`. This keeps schema knowledge in one
place — when a column is added, exactly one file changes.

### Schema

| Table | Key | Purpose |
|---|---|---|
| `users` | `discord_id` | Discord ↔ Riot account link, region routing |
| `matches` | `(match_id, discord_id)` | Per-player match stats |
| `ranks` | `discord_id` | Latest rank snapshot |
| `settings` | `guild_id` | Per-server config (leaderboard channel) |
| `streaks` | `discord_id` | Current streak + last seen match |
| `wallets` | `(discord_id, guild_id)` | Honeyfruit balance |
| `bets` | `bet_id` | Open/resolved bets |
| `wagers` | `(bet_id, bettor_discord_id)` | Individual wagers |
| `dodgeball_games` | `game_id` | Rate limiting for Mundo Dodgeball |
| `trivia_plays` | — | Daily trivia attempt tracking |
| `bot_state` | `key` | Generic key/value (last known patch version) |

### Why migrations use `PRAGMA table_info`

SQLite has no `ADD COLUMN IF NOT EXISTS`. The pattern used throughout:

```python
async with db.execute("PRAGMA table_info(matches)") as cursor:
    existing_columns = {row[1] async for row in cursor}
if "vision_score" not in existing_columns:
    await db.execute("ALTER TABLE matches ADD COLUMN vision_score INTEGER DEFAULT 0")
```

`CREATE TABLE IF NOT EXISTS` only runs once ever — it won't add columns to an
existing table. So tables are created with their original columns, and each new
column gets a check-then-add on every `init_db()` run. Safe to run repeatedly.

### Why `bot_state` is a generic key/value table

Rather than a dedicated table per value, `bot_state` holds arbitrary named
values — currently the last known patch version and per-user milestone
tracking (`milestone:{discord_id}:{games|wins|losses}`). Reusable for any
future "last known X" without another migration.

Note the stored patch version is Data Dragon's (`16.15`), not League's
marketing number (`26.15`). See section 14.

---

## 4. Guild Scoping — The Biggest Structural Lesson

**This caused a real bug and a painful mid-flight refactor. It's worth
understanding fully.**

The bot runs in multiple Discord servers. Data falls into three categories:

### Guild-scoped (stored per server)

`wallets`, `bets`, `settings`. Honeyfruit earned in one server has nothing to do
with another. Wallets use a composite primary key `(discord_id, guild_id)`.

### Not guild-scoped, but filtered at display time

`matches`, `ranks`, `streaks`. A League match is a real-world event tied to a
Riot account — storing it per-server would mean duplicating the same game N
times, which makes no sense.

Instead, commands filter by guild membership when *displaying*:

```python
async def get_registered_users_in_guild(guild) -> list[dict]:
    all_users = await get_all_registered_users()
    return [u for u in all_users if guild.get_member(u["discord_id"]) is not None]
```

**Consequence found later:** `sync_all_users()` reads `users` directly with no
membership check, so it keeps syncing people who have left every server. One
registration turned out to belong to someone who joined via a third server that
the bot was later removed from — they'd been getting synced daily, invisible to
every display. Filtering sync to current members would need `bot.guilds` access,
which `sync_all_users()` doesn't have. Deleting the row was simpler for one
case, but it would accumulate if the bot went public.

### The bug this caused

`/leaderboard` and `/memestats` originally pulled every registered user
globally, so members of one server appeared on another server's leaderboard.
Found once the bot was in two servers.

Betting was built *after* this fix and still shipped without guild scoping —
because the pattern wasn't applied automatically to a new feature. That required
a full refactor: schema change (composite key), every wallet/bet function
gaining a `guild_id` parameter, and a data migration.

**Standing rule going forward:** any new table storing per-user data gets a
`guild_id` from the first draft unless there's a specific reason it shouldn't.

### The migration that made it work

Old wallet rows had no guild association, and there was no way to recover which
server a balance belonged to. Solution: rename the old table to `wallets_legacy`
during `init_db()`, then in `on_ready()` — where `bot.guilds` is available —
credit each legacy balance into every server that user is currently a member of.
The migration drops the legacy table when done, so it runs exactly once.

This required running *after* Discord login, which is why it lives in
`on_ready()` rather than `init_db()`.

---

## 5. Riot API Integration

### Regional vs platform routing

Riot uses two routing schemes that don't map 1:1:

- **Regional** (`americas`, `europe`, `asia`) — account lookup, match data
- **Platform** (`na1`, `euw1`, `kr`) — rank/league data

Both are stored per user in `users`. `/register` presents a single dropdown of
platforms; `PLATFORM_TO_REGIONAL` derives the regional route so users only pick
one thing.

Originally hardcoded to NA. Adding region support touched five files, because
every call site needed to pass the user's stored region through. Only testing has been done
for NA regions. It's possible other regions don't work as intended, its also possible that the
user inputs their region incorrectly.

### Rate limiting

Development and personal keys share the same limits: roughly 20 requests/second
and 100 per 2 minutes. This caused repeated failures during backlog syncs.

Two mechanisms handle it:

1. **`asyncio.sleep(1.4)` between match fetches in `sync.py`** — paces requests
   rather than bursting.
2. **`Retry-After` handling in `riot_api.py`** — on a 429, read Riot's own
   header (typically ~101 seconds), sleep that long, retry. Up to 3 attempts.

The retry logic is what actually made backlog syncs complete rather than dying
partway through.

**Known consequence:** a sync with a large backlog can run for a long time,
because each rate limit hit costs ~101 seconds of waiting. This has real
downstream effects (see poll/sync coordination below).

### Why the delay is 1.4s specifically

100 requests per 2 minutes = one per 1.2 seconds. 1.4 adds a small buffer.

In practice this still hits the limit, because `get_match_ids` and `get_rank`
calls happen outside the delayed loop. A higher delay (2.0s) would trade a
longer sync for fewer 101-second stalls — probably faster overall. Not yet
changed or tested to see whatis actually faster.

### PUUIDs are encrypted per API key

Switching keys invalidates every stored PUUID — Riot returns
`400 Bad Request - Exception decrypting` on any call using one issued under a
different key. Symptom is every request failing at once with no obvious cause,
since it doesn't look like an auth error.

`repuuid.py` re-resolves all of them by Riot ID. Run it after any key change
(dev → personal → production). Match history is unaffected, since `matches`
joins on `discord_id` rather than PUUID.

---

## 6. Match Data: Two Paths In

### `poll.py` — live detection (every 90 seconds)

Checks each user's single most recent match ID against `streaks.last_match_id`.
If it changed, fetches the match and:

- Saves it to `matches`
- Updates streaks and fires streak alerts
- Checks for rank changes
- Runs the stat spike detector
- Checks milestones
- Resolves any open bets

**Why poll saves matches:** originally it only detected them, leaving `sync.py`
to save. That meant `/whoshouldiplay`, `/tierlist` server stats, and milestone
counts were stale for up to a week. Poll already had the full match data in
hand, so saving there was nearly free and made everything current within 90
seconds.

**Known gap:** poll only checks `count=1`. If someone plays several games
between ticks, only the most recent is seen live. The others wait for a sync.

### `sync.py` — batch backfill (daily + before weekly post)

Pulls up to 100 recent match IDs per user, skips ones already stored, fetches
and saves the rest.

Now functions as a **backstop** rather than the primary path — it catches games
poll missed (bot down, API errors, multiple games between ticks).

### Why `MATCHES_TO_CHECK` is 100

It was 15, which silently lost data for anyone playing more than 15 games
between syncs. Riot's `match-v5` caps `count` at 100, so that's the ceiling.

Combined with `get_existing_match_ids()` skipping already-stored matches, the
higher count is nearly free after the initial backfill.

### Poll/sync coordination

Both hit the same Riot API quota. During a backlog sync they competed, and both
failed.

Fix: `sync.py` exposes `sync_in_progress()` (checking `_SYNC_LOCK.locked()`),
and `poll.py` returns early if a sync is running.

That created a second problem: with poll paused for the length of a sync,
`last_match_id` went stale, so when poll resumed it saw old matches as new and
fired alerts for them. A spike alert for a 12-hour-old game was observed.

Fixed two ways. Sync advances `last_match_id` to the newest match Riot reported,
so poll doesn't rediscover anything it just processed. And poll gates alerts on
`save_match` returning True (sync didn't already store it) plus the match being
under an hour old — the first catches races, the second catches genuinely stale
detections.

### Why sync has no age cutoff

It used to skip anything older than a week, on the theory that leaderboards only
show a week anyway. That was wrong twice over.

Filtering at *storage* time meant all-time consumers — `/whoshouldiplay`,
career stats, `/nemesis`, milestone counts — could only ever see a week of
history, because that's all that was ever saved. One user had 8 matches stored
out of 58 available.

It also wasted the rate limit permanently. Matches rejected by the cutoff were
never saved, so `get_existing_match_ids()` never learned about them, so they got
re-fetched and re-discarded on every single sync. One user showed "43 new" every
day for matches that could never be stored.

The week window belongs at *query* time, where it already was —
`_weekly_stats_for_user`, meme stats, and `/nemesis` each pass their own `since`
to `get_recent_matches`. Removing the cutoff from sync left those untouched and
took stored history from ~50 matches to ~400.

**Rule this generalizes to:** the ingestion layer stores what it's given. Scoping
is the reader's job.

---

## 7. Game Mode Filtering

Riot stated via [@RiotGamesDevRel](https://x.com/RiotGamesDevRel) that certain
rotating modes wouldn't be available through the API, but one came through
anyway — `KIWI_JADE`, an internal codename, corresponding to ARAM Mayhem
Classic.

Its stats were wildly off normal play: 22 CS in 17 minutes, 13k gold, no item
data. Games like that distort win rates, performance scores, and every average
the bot computes.

**Decision: whitelist, not blacklist.**

```python
TRACKED_GAME_MODES = ("CLASSIC", "ARAM")
```

Reasoning: undocumented modes can't be enumerated. Riot's `gameModes.json` has a
long history of lagging behind the game, and a mode Riot says shouldn't be
exposed definitely won't be documented. A whitelist handles every future mode
without needing to react.

Applied in both `sync.py` and `poll.py` before `save_match`.

**Not fixed:** mode games saved before this filter existed are still in the
database, and `matches` has no `game_mode` column to find them by.

## 8. OP.GG Integration

### Why MCP

OP.GG publishes an MCP (Model Context Protocol) server at
`https://mcp-api.op.gg/mcp`. It's designed for AI tool-calling, but it's a plain
HTTP endpoint speaking JSON-RPC 2.0, so a Python client can use it directly via
the official `mcp` SDK.

This solved a real problem: matchup and meta data isn't available from Riot's
API, and scraping any website would be fragile and ToS-risky. To have commands
like `whoshouldiplay` or `tierlist` with real data attached to them required something
with a huge amount of data available for me to use instead of creating the data on my
own with the limited users I have.

### The two tools used

**`lol_get_lane_matchup_guide`** — live call, returns clean JSON. Provides
matchup tips, lane advantage, recommended play style, and a `counters` list of
~55 champions.

**`lol_get_champion_analysis`** — used by the cache fetch script. Returns
Python-repr-style text (not JSON), one champion at a time, but supports rank
bracket filtering.

### Why the tier list is cached, not live

`lol_list_lane_meta_champions` returns a whole lane in one call, but has **no
rank bracket parameter** — you get whatever bracket OP.GG decided, with no
control. Its ranking also doesn't match OP.GG's own website.

`lol_get_champion_analysis` *does* support brackets (`gold_plus`,
`emerald_plus`, `diamond_plus`, `all`) but only one champion per call. Getting a
full lane means ~170 calls.

Solution: `fetch_opgg_tierlist.py` runs manually after each patch, fetching
every champion × role × bracket into `data/opgg_tierlist.json`. Commands read
the cache instantly.

**Cost:** ~4,660 calls (233 champions × 5 lanes × 4 brackets), roughly an hour
per bracket. Same model as `fetch_ddragon.py` — patch-triggered, manual, not
scheduled.

**Why manual rather than a scheduled task:** at ~4 hours per run, a 12-hour
schedule would mean the bot spends a third of its life fetching. The meta
doesn't move fast enough to justify it.

**Incremental writes:** the cache is written after each bracket completes, so a
crash partway through keeps whatever finished rather than losing the whole run.
`_role_averages` is computed at the end, so a partial file has champion data but
no averages.

### Response format quirks

`lol_get_champion_analysis` returns Python-repr-style text:

```
LolGetChampionAnalysis(Data(Summary(266,false,false,AverageStats(...),
  [Position("TOP",Stats(309332,0.5,0.06,0.82,0.07,1.89,TierData(2,9,9,15)),...
```

Parsed with a regex targeting the `Position("TOP", Stats(...))` structure. The
tool's `desired_output_fields` filtering doesn't reach nested array fields, so
the full response is requested and narrowed in Python.

**Time sink worth recording:** several hours were lost assuming a
higher-precision JSON response existed. It didn't. `pick_rate` and `win_rate`
come back rounded to whole percents (`0.09`, not `0.0941`), confirmed
independently through Claude Desktop with the same MCP server. This is a hard
limitation of the data source.

**Hit rate is expected to be low.** ~1,000 of ~4,660 calls return usable data —
most champions aren't played in most roles, so those combinations legitimately
return nothing.

### Champion name format

OP.GG expects UPPER_SNAKE_CASE with punctuation stripped. Verified by testing
variants:

| Display name | OP.GG format |
|---|---|
| Dr. Mundo | `DR_MUNDO` |
| Kai'Sa | `KAISA` |
| Jarvan IV | `JARVAN_IV` |
| Nunu & Willump | `NUNU_WILLUMP` |

Numeric champion IDs also work (`36` for Dr. Mundo), but names are more
readable.

`to_opgg_champion_format()` in `opgg_client.py` is the single definition, used
by both `_resolve_champion` (user input) and the fetch script.

`_resolve_champion` additionally handles fuzzy user input — it strips all
separators for matching, so "dr mundo", "Dr. Mundo", and "drmundo" all resolve.
`CHAMPION_ALIASES` in `constants.py` maps shorthand like `j4`, `mundo`, `mf`.

**Gotcha:** the normalization regex must keep digits (`[^a-z0-9]`), or `j4`
becomes `j` and the alias lookup fails.

---

## 9. Meta vs Off-Meta Classification

`/tierlist` marks champions ⭐ (meta) or 🔍 (off-meta), with off-meta hidden by
default behind a toggle.

**Threshold: `pick_rate > 0.02` (2%).**

Reasoning: OP.GG's cached data rounds pick rate to whole percents, so a
displayed "1%" could really be anywhere from 0.51% to 1.49%. Setting the cutoff
at 2% pushes the ambiguous zone away from the boundary.

Validated against dpm.lol's own off-meta toggle, which appears to cut somewhere
around 1.0–1.3% — champions at exactly 1.0% (Heimerdinger) only appear with
their toggle on.

**Known flaw:** pick rate alone is a poor proxy for "is this a normal pick."
With ~55 viable mid champions, average pick rate is under 2% by definition, so
the threshold marks plenty of standard picks as off-meta. Annie mid — a
completely normal pick — gets flagged.

**Better approach if revisited:** rank-based (e.g. top 25 in the lane = meta)
rather than pick-rate-based. Wouldn't depend on precision at all.

**Note:** OP.GG's own website doesn't make this distinction — it shows all
champions with pick rate as one column. The toggle concept was borrowed from
dpm.lol, layered on top of OP.GG's data.

---

## 10. Performance Scoring (`/whoshouldiplay`)

The most involved feature. Originally ranked champions by win rate blended with
meta win rate; now scores how *well* you played.

### How it works

For each match, five stats are computed and scaled 0–100 against thresholds:

| Stat | Notes |
|---|---|
| `kda` | Assist-weighted for non-supports (see below) |
| `cs_per_min` | CS is given as a raw number and we convert it to a per minute figure based on the games duration |
| `damage_share` | Fraction of team damage (0.25 = 25%) |
| `gold_per_min` | Same thing as CS but with gold |
| `vision_per_min` | Vision score / minutes |

Each stat has `bad` and `good` cutoffs per **rank bracket** and **role**. At or
below `bad` scores 0; at or above `good` scores 100; linear in between.

Weighted per role via `PERFORMANCE_WEIGHTS` — supports lean on vision and KDA,
carries on damage and CS.

Final champion score blends personal performance with meta win rate, weighted by
sample size:

```python
confidence = min(personal_games / MIN_GAMES_FOR_PERSONAL_WEIGHT, 1.0)
score = (personal_performance * confidence) + (meta_score * (1 - confidence))
```

With `MIN_GAMES_FOR_PERSONAL_WEIGHT = 3`, one game gives your performance a
third of the weight; three or more gives it all.

### Why rate stats, not raw

Raw gold and CS favor long games. Per-minute makes games comparable regardless
of length. Damage share is inherently a ratio.

### Assist weighting

`ASSIST_WEIGHT = 0.5` for every role except support, where assists count fully.

Reasoning: a support's job produces assists by design, so full credit is correct
there. For a carry, 25 assists shouldn't read the same as 25 kills. This came
from a real game — ADC Senna 1/4/16 with only 14k damage — that scored well on raw
KDA despite being a poor carry performance.

### Bracket selection is automatic

`get_performance_bracket()` reads the player's stored rank and maps it via
`TIER_TO_BRACKET`. Iron–Gold → `gold_plus`, Platinum–Emerald → `emerald_plus`,
Diamond+ → `diamond_plus`, unranked → `all`.

Platinum and Emerald got their own bracket because lumping them with Gold scored
them too leniently.

### Thresholds are hand-written, not derived

The data needed to derive them (role-level CS/damage/gold/vision averages by
rank) isn't available from OP.GG's MCP tools — only KDA is. So thresholds are
researched manually and filled into `constants.py`.

**Calibration decision:** thresholds were tuned so real games land across the
0–100 range rather than centered on published Gold averages. Rationale: the
command ranks *your* champions against each other, so spread is what's useful.
If every champion scores 0–20 on damage share, that stat contributes nothing.

**Known limitation:** only `gold_plus` is calibrated against real data. The
other brackets are educated guesses until players in those ranks use the bot.

**Vision scores low on older matches.** The `vision_score` column was added
partway through, so anything stored before that has `0` and scores zero on that
stat regardless of how the game actually went. It corrects itself as new matches
accumulate, but early scores are dragged down.

**Also worth noting:** damage share may not scale with rank the way CS does.
It's a ratio — in a Diamond game, the pie is split among five stronger players,
so an ADC's share might stay flat or compress. If Diamond players score oddly
low there, flattening that threshold across brackets is the fix.

### Playrate-weighted role averages

`fetch_opgg_tierlist.py` computes `_role_averages` per bracket — KDA and win
rate averaged across champions in a role, **weighted by playrate**. Unweighted
would let a rarely-played champion skew the baseline as much as a popular one.

**Deliberately not feeding into scoring.** Deriving thresholds from these
averages was tried and reverted. Turning a population average into bad/good
cutoffs requires picking a spread (multipliers), and OP.GG's KDA counts assists
at full weight while ours weights them at 0.5 for non-supports — so a conversion
factor is needed that can't be derived from the data. That's three unvalidated
transformations between the measurement and the threshold. Hand-written values
tuned against real games in `tests/whoshouldiplay_test.py` are more trustworthy.

The KDA figures are still useful as a **sanity check** when writing thresholds
for a bracket with no real games to validate against — Gold+ ADC averaging 2.31
tells you roughly where the middle sits.

The win rate figures are useless: every game has a winner and a loser, so
aggregate win rate converges on ~50% for every role in every bracket by
definition.

---

## 11. Alerts

All fire from `poll.py` when a new match is detected. All post to the guild's
configured leaderboard channel, filtered to guilds where the player is actually
a member.

### Support champion styles

Damage share only means something for supports on damage-oriented picks — an
enchanter or engage support isn't expected to deal damage, so a low share isn't
a signal. Riot doesn't expose a support subtype anywhere, so
`SUPPORT_CHAMPION_STYLE` is a hand-maintained list splitting support champions
into Damage, Engage, and Enchanter.

**This is imprecise by nature.** Plenty of champions span multiple styles
depending on build and meta, and a static list can't capture that. It needs
occasional revisiting as champions shift. Champions missing from the list get a
note in the alert rather than being silently skipped, so gaps surface instead of
hiding.

No better approach was obvious — the alternative is deriving style from item
builds or damage patterns, which is a much larger project for a marginal gain.

### Streaks

Fires at multiples of 5 (5, 10, 15…), not every game past the threshold, and not
just once. `last_alert_streak` prevents duplicate alerts at the same length.

Streaks are pure consecutive counts with no time component — a genuine tilt
detector, not a weekly stat. Deliberate: "you're losing right now" is the useful
signal.

### Rank changes

Only fires on **tier** changes (Silver → Gold), never division changes (Silver
IV → Silver III), which would be noise. Demotions get their own message pool.
Master+ gets extra fanfare.

### Stat spikes

Compares a new game's CS/min, damage share, and vision/min against that player's
own rolling average. Fires at 25% deviation either direction, minimum 5 prior
games.

**Exclusions:** CS is skipped for supports (they don't farm) and for
non-`CLASSIC` modes (no lane creeps). Damage share is skipped for supports on
enchanter or engage picks. Vision is checked for supports only.

### Age and freshness gating

Milestones, streaks, rank changes, and stat spikes only fire when the match is
both freshly played (within `SECONDS_PER_HOUR`) and newly saved by poll
(`save_match` returned True). Poll pauses entirely while a sync holds the lock,
and a long backlog sync can stall it for hours — during which `last_match_id`
goes stale. When poll resumes it sees an old match as "new" and used to fire
alerts for games sync had already stored. Observed: multiple milestone alerts
("10 wins logged") for someone who wasn't actively playing.

Bet resolution has no gate — bets have to resolve or stakes never pay out,
including when sync saved the match before poll noticed it.

### Milestones

Round-number totals for games, wins, and losses: 1, 10, 25, 50, 100, 200, 300,
500, 750, 1000, then every 500. Losses get roasted, wins get celebrated.

Counts come from `get_recent_matches(discord_id, 0)` — a full-table read per
check. Fine at this scale; the first thing to optimize if it grows.

**Deduplication:** each counter's last-alerted value is stored in `bot_state`
under `milestone:{discord_id}:{games|wins|losses}`. Without it, a counter
sitting at a threshold re-fires on every subsequent match — hit 50 losses, win
the next game, and the loss milestone alerts again because losses didn't move
but the check still ran.

Only the first milestone found per match fires, so a game crossing two
thresholds at once (games and wins) only announces one. The other is recorded as
alerted regardless.

---

## 12. Honeyfruit Economy

Fake currency, guild-scoped. Wallets are created lazily at 1000 on first use, so
`/register` didn't need changing.

### Earning

Three sources beyond the starting 1000:

- **`/dailybonus`** — 100 Honeyfruit, once per 24 hours, guild-scoped.
- **`/trivia`** — 100 per correct answer, capped at 5 questions per day.
  Questions are generated from cached Data Dragon data: guess the champion from
  a quote (reusing `/wisdom`'s pool) or from an ability name and icon.
  Multiple-choice via buttons rather than free text, which sidesteps typo and
  spelling issues entirely.
- **Mundo Dodgeball** — zero-sum between players, not new currency.

Both `/dailybonus` and `/trivia` track their cooldowns in dedicated tables
(`wallets.last_daily_claim`, `trivia_plays`) rather than in `bot_state`, since
both are per-user-per-guild rather than single values.

### Betting

`/openbet` — a player opens betting on their **own** next game. Others wager
Win/Loss. Flat odds: correct predictions double the stake.

Stakes are deducted immediately on placement (true escrow) and paid out on
resolution. Resolution hooks into `poll.py`'s existing match detection.

Changing a bet refunds the old stake before deducting the new one — otherwise
lowering a wager would silently keep the difference.

`/openbet` requires a configured leaderboard channel, and fails clearly if
there isn't one. Otherwise a bet would open with nobody able to see it.

### Mundo Dodgeball

Wagered 1v1 mini-game. Three rounds of narrated Infected Bonesaw throws, most
hits wins the pot. Button-based accept/decline with a 30-second timeout.

Rate limited to 3 games per challenger per 24 hours (not per pair), with the
error message showing time remaining.

### Kashdaji Queen

Discord role auto-assigned weekly to whoever holds the most Honeyfruit in that
server. Announcement text differs for claiming, retaining, or first-time
assignment.

Requires the bot's role to sit **above** the Kashdaji Queen role in the server's
role hierarchy, and to have Manage Roles permission.

---

## 13. Scheduling

Three separate task loops in `admin/cog.py`:

| Task | Schedule | Does |
|---|---|---|
| `daily_sync` | 06:00 UTC daily | `sync_all_users()` only |
| `weekly_leaderboard` | Mondays 12:00 UTC | Sync, then post embeds + meme stats + Kashdaji Queen |
| `patch_check` | Every 24 hours | Check Data Dragon for a new patch |

**Why sync and the leaderboard post were split:** they were bundled on the same
weekly schedule for no real reason. Data should be fresh daily; the leaderboard
post is a weekly event.

**Why the weekly post still syncs first:** redundant with the daily sync and live
poll saving, but guarantees the post reflects the freshest possible data.
Deliberate choice for accuracy over efficiency.

Six hours apart so they don't collide on Mondays. `_SYNC_LOCK` prevents
overlapping runs regardless.

`patch_check` uses `hours=24` rather than a fixed time, so it drifts with
restarts and fires once on startup. Fine for something that only matters twice
a month.

**Collision risk beyond the bot:** unattended-upgrades runs on its own schedule
and has overlapped with the daily sync. An OpenSSL upgrade mid-sync killed the
process (see section 16). Nothing coordinates these — the mitigation is PM2
restart config, not scheduling.

---

## 14. Patch Alerts

Polls Data Dragon's `versions.json` every 24 hours, compares against
`bot_state["last_known_patch_version"]`, and posts a link when it changes.

First run baselines silently rather than announcing a patch that may have been
live for days.

### The version number problem

**Data Dragon and League use different version schemes.** Data Dragon reports
`16.15.x` while the marketing patch is 26.15 — Riot switched League to
year-based numbering in 2025 while Data Dragon's sequential versioning kept
climbing.

Riot's API doesn't expose the marketing patch number anywhere. Match data's
`gameVersion` uses the Data Dragon scheme too.

Workaround: `PATCH_VERSION_OFFSET = 10` applied to the major version.

**Fragile.** Breaks if either scheme changes independently. The symptom would be
404 links again, which is at least obvious.

### The URL pattern

```
https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-{major}-{minor}-notes/
```

Derived from one real example, not documented. Riot has changed this format
before.

**Also known:** Data Dragon can flip to a new version before the patch notes
page exists or before the patch reaches all regions, so an alert can arrive
early with a link that 404s temporarily.

**Unverified.** The offset was added after the 26.15 alert posted a broken
16.15 link. It hasn't been through a real patch since, so the next one is the
first live test.

---

## 15. Content vs Config

A distinction applied throughout, deciding what goes in `constants.py`:

**In `constants.py`** — values that are shared, duplicated, or tunable:
thresholds, intervals, time windows, tier orders, position mappings, API config.

**Stays local to its module** — content and domain data that only one file uses:
`LOSS_MESSAGES`, `WIN_MESSAGES`, `CHAMPION_QUOTES`, `EXCUSES`, `HIT_MESSAGES`,
`STAT_SHARDS`, `REGION_CHOICES`.

Reasoning: moving message pools to `constants.py` wouldn't reduce duplication
(they're not duplicated) or improve consistency (nothing else references them).
It'd just relocate them away from the code that reads them.

**Also deliberately not centralized:** `DATA_DIR` (depends on each file's own
location on disk) and `_SYNC_LOCK` (a live runtime object, not a value).

**Known inconsistency:** `SUPPORT_CHAMPION_STYLE` and `CHAMPION_ALIASES` are
both content by this rule — hand-maintained lists with a single consumer each —
but live in `constants.py` anyway. They're tuning data more than message
content, and both are things you'd expect to edit deliberately rather than
alongside code.

### Position vocabularies

Four different formats exist for the same five roles:

| Context | Format |
|---|---|
| Discord display | `Mid` |
| Riot API | `MIDDLE` |
| OP.GG request | `mid` |
| OP.GG response | `MID` |

Consolidated into one master `POSITIONS` list in `constants.py`, with everything
else derived from it. One place to edit, at the cost of some indirection. Can we as a
community just use one format?

---

## 16. Bugs Worth Remembering

Fixes whose causes weren't obvious, recorded so they're not re-derived:

### Members intent

`guild.get_member(discord_id)` returned `None` for real members, silently
breaking every guild-scoped feature. `discord.Intents.default()` doesn't include
members, so the member cache was empty.

Fix: `intents.members = True` **and** enabling "Server Members Intent" in the
Discord Developer Portal. Both are required.

### Embed field limit

`/compare` used a 3-column grid with spacer fields: 2 headers + 1 spacer + (8
stats × 3 fields) = 27 fields. Discord's limit is 25.

Fix: one field per player with multi-line text. Simpler and more readable.

### Buffered output

Python buffers stdout when not attached to a terminal, so mid-run prints never
reached PM2's logs — meaning long syncs appeared to hang with no output.

Fix: `python -u` in `run_bot.sh`.

**This one is worth remembering because it made every other bug harder to
diagnose.** Debugging was effectively blind until it was found.

### ExceptionGroup wrapping

`OpggError` raised inside the MCP client's task group got wrapped in nested
`ExceptionGroup`s, so `except OpggError` never caught it — users saw the generic
"Something went wrong" instead of the real message.

Fix: catch `BaseException` at the outermost level in `_call_tool` and unwrap
through nested groups to find the real message.

Also learned: `except*` can't be mixed with regular `except` in the same `try`,
and can't contain `return`.

### Counter win rate perspective

`/matchup` labeled counter win rates backwards. OP.GG's `Counter.win` field
counts **your champion's** wins in that matchup, not the counter's.

Caught because three separate "counters" all showed 48–49% — impossible if they
genuinely countered you. Confirmed against OP.GG's website, which frames the
same numbers from the champion's perspective ("Weak against: 40%" means you win
40%).

Fix: split into "weak against" (under 50%) and "strong against" (over 50%),
matching OP.GG's own framing.

### Position data on old matches

36 matches predate the `position` column and have it blank, so they're excluded
from position-filtered stats. Surfaced as a Tristana record showing 0-2 when it
should have been 1-1.

**Deliberately not fixed** — they'll age out of most windows, and a backfill
script wasn't worth the effort.

### PUUIDs are encrypted per API key

Switching from the dev key to a personal key broke every Riot call at once —
`400 Bad Request - Exception decrypting`. PUUIDs are encrypted per key, so
stored ones from a previous key are unreadable.

Hard to diagnose because it doesn't look like an auth error. `repuuid.py`
re-resolves them all by Riot ID. Run after any key change.

### OpenSSL upgraded underneath a running process

The bot died overnight with no traceback and stayed down 10 hours.
`unattended-upgrades` had replaced `libssl3t64` and `openssl` at 06:51 while a
sync was running. Existing SSL connections broke, the process crashed, PM2
restarted it into the same broken state repeatedly, then hit its default
restart limit and gave up permanently.

Two contributing factors: `run_bot.sh` had recently lost its `while true` loop
(previously masking this by restarting independently of PM2), and PM2 defaults
to giving up after 15 rapid restarts.

Fix: `pm2 start run_bot.sh --max-restarts 0 --restart-delay 5000`. Can't prevent
the crash, but recovery is now automatic.

### Duplicate spike alerts

Non-supports got the damage share message twice. The support-style check was
added as a second block, but its `else` branch set the check flag to `True` for
non-supports — so they passed through both the original block and the new one.

Fix: two mutually exclusive blocks, one gated on `is_support` and one on
`not is_support`, with no shared flag between them.

---

## 17. Known Limitations

Things that are wrong or incomplete, and why they're being lived with:

| Limitation | Notes |
|---|---|
| Personal API key rate limits | 20/sec, 100/2min. Syncs are slow as a result. Production key pending Riot approval. |
| OP.GG pick rate precision | Rounded to whole percents at the source. Confirmed independently. Not fixable. |
| Matches with blank position | Predate the column. Excluded from position stats. Will age out. |
| Matches with zero vision score | Predate the column. Score 0 on that stat in performance scoring until they age out. |
| Untracked mode games in DB | Saved before the whitelist existed. No `game_mode` column to find them by. |
| Non-gold thresholds | Educated guesses until players in those brackets use the bot. |
| Patch version offset | Fragile +10 workaround. Untested against a real patch. |
| OP.GG tier ranking ≠ website | The MCP tool's `rank` doesn't match op.gg's site. Cause unknown; likely a different internal bracket. |
| `matches` grows unbounded | No pruning. Fine at this scale. |
| Poll misses multi-game sessions | Only checks `count=1`. Sync catches the rest. |
| Poll pauses during sync | `last_match_id` goes stale. Safeguards are in place, but the interaction is subtle. |
| Meta/off-meta threshold | 2% flags normal picks as off-meta. Rank-based would be better. |
| Sync includes users who left | `sync_all_users()` has no membership check, so it keeps fetching for people no longer in any server. One such registration was found and deleted manually. |
| Filtered matches re-fetched | Mode and remake skips are never saved, so they're re-fetched every sync. One call per user, not worth a table. |

---

## 18. Deployment

- **VPS** under PM2, started with
  `pm2 start run_bot.sh --name league-bot --max-restarts 0 --restart-delay 5000`
- **`run_bot.sh`** activates the venv and runs `python -u -m leaguebot.bot`
- **Deploy:** `git pull` on the VPS, then `pm2 restart league-bot --update-env`

**`--update-env` matters** — PM2 caches environment variables from the original
`pm2 start`, so a plain restart can serve stale `.env` values.

**`--max-restarts 0` matters** — PM2 defaults to giving up after 15 rapid
restarts and marking the process stopped permanently. That turned a brief
OpenSSL-upgrade crash into 10 hours of downtime (section 16).

### Website

`scuttlebuddy.lol` — static HTML served by Nginx over HTTPS (Let's Encrypt via
Certbot, auto-renewing). DNS A records at Namecheap point `@` and `www` to the
VPS.

Exists because **Riot requires one for production API key approval**. A Discord
invite link alone doesn't satisfy it — they want a page documenting what the bot
does, where to add it, and linking to Terms of Service and Privacy Policy, plus
a `riot.txt` at the domain root for ownership verification. **HTTPS is
mandatory** — the application form rejects `http://` URLs.

Deliberately basic. A full web app would be building for scale that doesn't
exist yet.

Files live in `/var/www/scuttlebuddy.lol/`, owned by `www-data`. Note: serving
from `/root/` doesn't work — Nginx runs as `www-data` and can't traverse into
root's home directory. Certbot edited `/etc/nginx/sites-enabled/scuttlebuddy.lol`
directly, which isn't in the site repo — don't overwrite it from an older copy.

### Riot compliance

- Uses Riot assets under the "Legal Jibber Jabber" fan content policy, with the
  required attribution in the site footer
- Bot set to non-public in the Developer Portal while awaiting the production
  key, so a top.gg listing can't bring in strangers early
- **PUUIDs are key-encrypted** — see section 5. Run `repuuid.py` after any key
  change.

---

## 19. Things Deliberately Not Built

Recorded so the reasoning isn't lost:

**Live champ select awareness.** Riot's Live Client Data API is localhost-only
— it runs on the player's own machine. A bot on a VPS has no path to it. Would
require a separate companion app installed on each user's PC. Out of scope for a
Discord bot.

**Composite performance score from scratch (z-scores).** Sites like OP.GG derive
scores by normalizing stats against role/champion baselines built from millions
of games. With ~6 users, there's no sample to build baselines from. The
threshold approach is the workable version.

**Champion counter graph from match-v5.** Mining high-elo match data to build
matchup win rates would take millions of API calls. Solved instead by using
OP.GG's pre-aggregated data.

**Test bot.** A second bot instance would need its own token, database, and
would double Riot API usage against the same key. Unit tests on the pure logic
were judged a better use of effort.

**Multi-language support.** Infrastructure is a day's work; the content is the
real project. Machine-translating the roast pools would strip the personality
that's most of the bot's value.

**Deriving KDA thresholds from OP.GG role averages.** Built, then reverted.
Turning a population average into bad/good cutoffs needs a spread multiplier,
and OP.GG's KDA weights assists fully while ours halves them for non-supports —
so a conversion factor is needed that can't be derived from the data. Three
unvalidated transformations between measurement and threshold. Hand-written
values tuned against real games are more trustworthy. (Section 10.)

**Blending server stats into OP.GG's tier numbers.** With ~6 users, your data
would be a rounding error against millions of games — merging them changes
nothing. Making it matter would mean deliberately overweighting local data,
which produces a number that represents neither dataset honestly. Solved by
showing them side by side instead: `/tierlist` displays the global tier and your
server's own record on that champion as separate values.

---

## 20. If Picking This Up Later

Immediate open items:

1. **Riot production key** — personal key approved and in use; production key
   still pending. Everything gated on rate limits improves once it lands.
2. **Threshold calibration** — only `gold_plus` is validated. Use
   `tests/whoshouldiplay_test.py` to inspect scoring against real matches.
   (Note: `tests/` isn't tracked in git.)
3. **Patch URL offset** — the `+10` fix hasn't been through a real patch yet.
   Next one is the first live test.
4. **Sync delay** — 1.4s still hits the rate limit. Try 2.0s.

After each patch:

```bash
python -m leaguebot.fetch_ddragon          # minutes
python -m leaguebot.fetch_opgg_tierlist    # ~1 hour per rank bracket
```

After any API key change:

```bash
python -m leaguebot.repuuid                # seconds
```