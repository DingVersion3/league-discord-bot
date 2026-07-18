# Core betting logic: opening bets, placing wagers, and resolving payouts.
# Bets are flat-odds — win your prediction, double your wager back; lose it, it's gone.
import time

from leaguebot.db import get_open_bet, create_bet, place_wager as db_place_wager, get_wagers_for_bet, resolve_bet, adjust_wallet, get_wallet


async def open_bet(tracked_discord_id: int, guild_id: int) -> tuple[int | None, str | None]:
    # Returns (bet_id, error_message). error_message is None on success.
    existing = await get_open_bet(tracked_discord_id, guild_id)
    if existing:
        return None, "You already have an open bet — wait for it to resolve first."

    bet_id = await create_bet(tracked_discord_id, guild_id, int(time.time()))
    return bet_id, None


async def place_bet(bet_id: int, bettor_discord_id: int, tracked_discord_id: int,
                     guild_id: int, prediction: str, amount: int) -> str | None:
    # Returns an error message on failure, else None on success.
    if bettor_discord_id == tracked_discord_id:
        return "You can't bet on your own game."

    if prediction not in ("win", "loss"):
        return "Prediction must be 'win' or 'loss'."

    if amount <= 0:
        return "Bet amount must be greater than 0."

    return await db_place_wager(bet_id, bettor_discord_id, guild_id, prediction, amount)


async def resolve(bet_id: int, guild_id: int, tracked_won: bool) -> list[dict]:
    # Pays out winners, resolves the bet, returns a summary list for messaging: 
    # [{"discord_id": ..., "prediction": ..., "amount": ..., "won": bool, "payout": int}]
    wagers = await get_wagers_for_bet(bet_id)
    outcome = "win" if tracked_won else "loss"
    results = []

    for wager in wagers:
        correct = wager["prediction"] == outcome
        payout = wager["amount"] * 2 if correct else 0
        if correct:
            await adjust_wallet(wager["bettor_discord_id"], guild_id, payout)

        results.append({
            "discord_id": wager["bettor_discord_id"],
            "prediction": wager["prediction"],
            "amount": wager["amount"],
            "won": correct,
            "payout": payout,
        })

    await resolve_bet(bet_id, int(time.time()))
    return results