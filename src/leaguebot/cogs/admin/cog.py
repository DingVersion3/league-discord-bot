# Admin only commands and there functions
# /setleaderboardchannel: pick where the weekly leaderboard auto-posts.
# /syncnow: manually trigger the weekly sync + leaderboard post
# Weekly task: syncs fresh data and auto-posts the leaderboard on schedule.
import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from leaguebot.db import set_leaderboard_channel, get_leaderboard_channel
from leaguebot.cogs.leaderboard.sync import sync_all_users
from leaguebot.cogs.leaderboard.board import build_leaderboard_embed, get_top_honeyfruit_holder
from leaguebot.cogs.memestats.stats import build_meme_stats_embed

ROLE_NAME = "Kashdaji Queen"


class AdminCog(commands.Cog):
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
                for stat in ("win_rate", "kda", "wins", "rank", "double_kills", "triple_kills", "quadra_kills", "penta_kills", "honeyfruit"):
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
                    for stat in ("win_rate", "kda", "wins", "rank", "double_kills", "triple_kills", "quadra_kills", "penta_kills", "honeyfruit"):
                        embed = await build_leaderboard_embed(guild, stat)
                        await channel.send(embed=embed)
                    meme_embed = await build_meme_stats_embed(guild)
                    await channel.send(embed=meme_embed)

            await self.assign_kashdaji_queen(guild)

    @weekly_sync.before_loop
    async def before_weekly_sync(self):
        await self.bot.wait_until_ready()

    async def assign_kashdaji_queen(self, guild: discord.Guild) -> None:
        top_holder = await get_top_honeyfruit_holder(guild.id)
        if not top_holder:
            return

        role = discord.utils.get(guild.roles, name=ROLE_NAME)
        if role is None:
            try:
                role = await guild.create_role(name=ROLE_NAME, color=discord.Color.gold())
            except discord.Forbidden:
                print(f"[ADMIN] missing permission to create role in {guild.name}")
                return

        winner = guild.get_member(top_holder["discord_id"])
        if winner is None:
            return

        try:
            for member in role.members:
                if member.id != winner.id:
                    await member.remove_roles(role)
            if role not in winner.roles:
                await winner.add_roles(role)
        except discord.Forbidden:
            print(f"[ADMIN] missing permission to manage roles in {guild.name}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))