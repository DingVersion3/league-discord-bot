import discord
from discord import app_commands
from discord.ext import commands, tasks

from . import alerts, poll
from leaguebot.db import get_streak
from leaguebot.constants import INTERVAL


class AlertsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.poll_loop.start()

    def cog_unload(self):
        self.poll_loop.cancel()

    @tasks.loop(seconds=INTERVAL)
    async def poll_loop(self):
        await poll.check_for_new_results(self.bot)

    @poll_loop.before_loop
    async def before_poll_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="streak", description="Check your current win/loss streak")
    @app_commands.describe(member="Whose streak to check (defaults to you)")
    async def streak(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        row = await get_streak(member.id)

        if not row or row["streak_type"] == "none":
            await interaction.response.send_message(f"{member.display_name} has no active streak.")
            return

        emoji = "🔥" if row["streak_type"] == "win" else "💀"
        await interaction.response.send_message(
            f"{emoji} {member.display_name} is on a {row['current_streak']}-game {row['streak_type']} streak."
        )


async def setup(bot):
    await bot.add_cog(AlertsCog(bot))