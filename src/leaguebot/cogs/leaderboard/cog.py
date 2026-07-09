# /setleaderboardchannel: pick where the weekly leaderboard auto-posts.
# /leaderboard: on-demand leaderboard, ranked by a chosen stat.
# Weekly task: syncs fresh data and auto-posts the leaderboard.

import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from leaguebot.db import set_leaderboard_channel, get_leaderboard_channel
from leaguebot.cogs.leaderboard.sync import sync_all_users
from leaguebot.cogs.leaderboard.board import build_leaderboard_embed

STAT_CHOICES = [
    app_commands.Choice(name="Win Rate", value="win_rate"),
    app_commands.Choice(name="Average KDA", value="kda"),
    app_commands.Choice(name="Total Wins", value="wins"),
    app_commands.Choice(name="Solo Queue Rank", value="rank"),
]


class LeaderboardCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.weekly_sync.start()

    def cog_unload(self):
        self.weekly_sync.cancel()

    @app_commands.command(name="setleaderboardchannel", description="Set the channel for weekly leaderboard posts")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setleaderboardchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await set_leaderboard_channel(interaction.guild_id, channel.id)
        await interaction.response.send_message(f"Weekly leaderboard will post to {channel.mention}.")

    @app_commands.command(name="leaderboard", description="Show the server leaderboard")
    @app_commands.describe(stat="Which stat to rank by")
    @app_commands.choices(stat=STAT_CHOICES)
    async def leaderboard(self, interaction: discord.Interaction, stat: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await build_leaderboard_embed(stat.value)
        await interaction.followup.send(embed=embed)

    @tasks.loop(time=datetime.time(hour=12, minute=0))  # runs daily at 12:00 UTC, checks day inside
    async def weekly_sync(self):
        if datetime.datetime.utcnow().weekday() != 0:  # 0 = Monday
            return

        await sync_all_users()

        for guild in self.bot.guilds:
            channel_id = await get_leaderboard_channel(guild.id)
            if channel_id:
                channel = guild.get_channel(channel_id)
                if channel:
                    embed = await build_leaderboard_embed("win_rate")
                    await channel.send(embed=embed)

    @weekly_sync.before_loop
    async def before_weekly_sync(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))