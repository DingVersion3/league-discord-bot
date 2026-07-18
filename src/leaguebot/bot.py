# Bot entrypoint. Run with: python -m leaguebot.bot
import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from leaguebot.db import init_db, migrate_legacy_wallets

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# Optional: syncing commands to a single guild is near-instant, vs. up to an hour for a global sync. Set this in .env while you're testing.
GUILD_ID = os.getenv("DISCORD_GUILD_ID")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")

    # One-time migration: credits any pre-guild-scoping wallet balances into
    # every server the owner is currently a member of. No-ops once the legacy
    # table is gone.
    guild_member_ids = {
        guild.id: [member.id for member in guild.members] for guild in bot.guilds
    }
    await migrate_legacy_wallets(guild_member_ids)

    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} command(s) globally (may take up to an hour to appear)")
    # only uncomment this out for debugging
    # global_cmds = await bot.tree.fetch_commands()
    # print(f"Global: {[c.name for c in global_cmds]}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    import traceback
    print(f"[COMMAND ERROR] /{interaction.command.name if interaction.command else 'unknown'}: {error}")
    traceback.print_exception(type(error), error, error.__traceback__)

    if interaction.response.is_done():
        await interaction.followup.send("Something went wrong running that command.", ephemeral=True)
    else:
        await interaction.response.send_message("Something went wrong running that command.", ephemeral=True)


async def main():
    await init_db()
    async with bot:
        await bot.load_extension("leaguebot.cogs.randomchamp.cog")
        await bot.load_extension("leaguebot.cogs.recap.cog")
        await bot.load_extension("leaguebot.cogs.leaderboard.cog")
        await bot.load_extension("leaguebot.cogs.memestats.cog")
        await bot.load_extension("leaguebot.cogs.alerts.cog")
        await bot.load_extension("leaguebot.cogs.betting.cog")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())