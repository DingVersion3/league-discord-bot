# /memestats: on-demand weekly meme stats digest.
# /roast: Roast or compliment(or leave it up to chance) someone based on their most recent game
import discord
import random
from discord import app_commands
from discord.ext import commands
from .roast import get_latest_match, generate_line
from .wisdom import get_random_quote

from leaguebot.cogs.memestats.stats import build_meme_stats_embed


class MemeStatsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="memestats", description="Show this week's meme stats")
    async def memestats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = await build_meme_stats_embed(interaction.guild)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="roast", description="Roast or compliment someone based on their most recent game")
    @app_commands.describe(user="Who to target", mode="Roast, compliment, or leave it to chance")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Roast", value="roast"),
        app_commands.Choice(name="Compliment", value="compliment"),
        app_commands.Choice(name="Random", value="random"),
    ])
    async def roast(self, interaction: discord.Interaction, user: discord.Member, mode: app_commands.Choice[str] | None = None):
        await interaction.response.defer()

        match = await get_latest_match(user.id)
        if not match:
            await interaction.followup.send(f"{user.display_name} has no match history to roast (or compliment).")
            return

        chosen_mode = mode.value if mode else "random"
        if chosen_mode == "random":
            chosen_mode = random.choice(["roast", "compliment"])

        line = generate_line(match, chosen_mode)
        await interaction.followup.send(f"{user.mention} {line}")


    @app_commands.command(name="wisdom", description="Ancient League wisdom, from League Champions")
    async def wisdom(self, interaction: discord.Interaction):
        await interaction.response.defer()
        champion, quote = get_random_quote()
        await interaction.followup.send(f"*\"{quote}\"*\n- {champion}")


async def setup(bot: commands.Bot):
    await bot.add_cog(MemeStatsCog(bot))