# /trivia: a daily-limited League trivia quiz. Correct answers earn Honeyfruit.
import time

import discord
from discord import app_commands
from discord.ext import commands

from leaguebot.db import log_trivia_play, count_recent_trivia_plays, adjust_wallet, get_oldest_recent_trivia_play
from leaguebot.constants import SECONDS_PER_DAY, TRIVIA_REWARD, MAX_TRIVIA_PER_DAY
from .questions import generate_question


class TriviaView(discord.ui.View):
    def __init__(self, user_id: int, guild_id: int, correct_answer: str):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.guild_id = guild_id
        self.correct_answer = correct_answer
        self.answered = False

    async def _handle_answer(self, interaction: discord.Interaction, chosen: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your trivia question.", ephemeral=True)
            return

        self.answered = True
        for item in self.children:
            item.disabled = True

        await log_trivia_play(self.user_id, self.guild_id, int(time.time()))

        if chosen == self.correct_answer:
            new_balance = await adjust_wallet(self.user_id, self.guild_id, TRIVIA_REWARD)
            await interaction.response.edit_message(
                content=f"✅ Correct! It was **{self.correct_answer}**. +{TRIVIA_REWARD} Honeyfruit (now {new_balance}).",
                view=self,
            )
        else:
            await interaction.response.edit_message(
                content=f"❌ Nope — it was **{self.correct_answer}**. Better luck next time.",
                view=self,
            )
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


def _make_button(choice: str) -> discord.ui.Button:
    button = discord.ui.Button(label=choice, style=discord.ButtonStyle.primary)

    async def callback(interaction: discord.Interaction):
        view: TriviaView = button.view
        await view._handle_answer(interaction, choice)

    button.callback = callback
    return button


class TriviaCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="trivia", description="Answer a League trivia question for Honeyfruit")
    async def trivia(self, interaction: discord.Interaction):
        since = int(time.time()) - SECONDS_PER_DAY
        plays_today = await count_recent_trivia_plays(interaction.user.id, interaction.guild_id, since)

        if plays_today >= MAX_TRIVIA_PER_DAY:
            oldest = await get_oldest_recent_trivia_play(interaction.user.id, interaction.guild_id, since)
            seconds_remaining = max((oldest + SECONDS_PER_DAY) - int(time.time()), 0) if oldest else 0
            hours = seconds_remaining // 3600
            minutes = (seconds_remaining % 3600) // 60
            await interaction.response.send_message(
                f"You've already played {MAX_TRIVIA_PER_DAY} trivia questions today. "
                f"Try again in {hours}h {minutes}m.",
                ephemeral=True,
            )
            return

        question = generate_question()
        view = TriviaView(interaction.user.id, interaction.guild_id, question["correct"])
        for choice in question["choices"]:
            view.add_item(_make_button(choice))

        embed = discord.Embed(title="🧠 League Trivia", description=question["prompt"], color=discord.Color.blue())
        if question["image_url"]:
            embed.set_thumbnail(url=question["image_url"])
        embed.set_footer(text=f"{plays_today + 1}/{MAX_TRIVIA_PER_DAY} questions today")

        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(TriviaCog(bot))