# /setleaderboardchannel: pick where the weekly leaderboard auto-posts.
# /leaderboard: on-demand leaderboard, ranked by a chosen stat.
# Weekly task: syncs fresh data and auto-posts the leaderboard.

import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from leaguebot.db import set_leaderboard_channel, get_leaderboard_channel
from leaguebot.cogs.leaderboard.sync import sync_all_users
from leaguebot.cogs.leaderboard.board import build_leaderboard_embed, build_compare_embed
from leaguebot.cogs.memestats.stats import build_meme_stats_embed

STAT_CHOICES = [
    app_commands.Choice(name="Win Rate", value="win_rate"),
    app_commands.Choice(name="Average KDA", value="kda"),
    app_commands.Choice(name="Total Wins", value="wins"),
    app_commands.Choice(name="Solo Queue Rank", value="rank"),
    app_commands.Choice(name="Double Kills", value="double_kills"),
    app_commands.Choice(name="Triple Kills", value="triple_kills"),
    app_commands.Choice(name="Quadra Kills", value="quadra_kills"),
    app_commands.Choice(name="Penta Kills", value="penta_kills"),
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

    @app_commands.command(name="syncnow", description="Manually trigger the weekly sync + leaderboard post (admin only)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def syncnow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        summary = await sync_all_users()
        errors = {uid: s["error"] for uid, s in summary.items() if s["error"]}
        total_added = sum(s["matches_added"] for s in summary.values())

        channel_id = await get_leaderboard_channel(interaction.guild_id)
        posted = False
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                for stat in ("win_rate", "kda", "wins", "rank", "double_kills", "triple_kills", "quadra_kills", "penta_kills"):
                    embed = await build_leaderboard_embed(interaction.guild, stat)
                    await channel.send(embed=embed)
                meme_embed = await build_meme_stats_embed(interaction.guild)
                await channel.send(embed=meme_embed)
                posted = True

        status = f"Synced {len(summary)} user(s), {total_added} new match(es) added."
        if errors:
            status += f"\n{len(errors)} error(s): {errors}"
        status += f"\nPosted to leaderboard channel: {'yes' if posted else 'no (not set, or channel missing)'}"

        await interaction.followup.send(status)

    @app_commands.command(name="leaderboard", description="Show the server leaderboard")
    @app_commands.describe(stat="Which stat to rank by")
    @app_commands.choices(stat=STAT_CHOICES)
    async def leaderboard(self, interaction: discord.Interaction, stat: app_commands.Choice[str]):
        await interaction.response.defer()
        embed = await build_leaderboard_embed(interaction.guild, stat.value)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="compare", description="Compare two players' stats for the week")
    @app_commands.describe(user1="First player", user2="Second player")
    async def compare(self, interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
        await interaction.response.defer()
        embed = await build_compare_embed(interaction.guild, user1, user2)
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
                    for stat in ("win_rate", "kda", "wins", "rank", "double_kills", "triple_kills", "quadra_kills", "penta_kills"):
                        embed = await build_leaderboard_embed(guild, stat)
                        await channel.send(embed=embed)
                    meme_embed = await build_meme_stats_embed(guild)
                    await channel.send(embed=meme_embed)

    @weekly_sync.before_loop
    async def before_weekly_sync(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))