# Responds when someone @-mentions the bot. No commands, no data -- just
# ScuttleBuddy talking back.
import time

import discord
from discord.ext import commands

from leaguebot.helpers import log
from leaguebot.db import get_bot_state, set_bot_state
from .responses import get_response

# Per-user cooldown, so a spammed mention doesn't become a spammed channel.
MENTION_COOLDOWN_SECONDS = 10


class SentienceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_response: dict[int, float] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore every bot, not just ourselves -- two bots mentioning each
        # other would loop forever.
        if message.author.bot:
            return

        # Check the raw content rather than message.mentions: replying to one
        # of the bot's messages puts it in mentions even with no @ typed, and
        # responding to every reply would be obnoxious.
        mention_forms = (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>")
        if not any(form in message.content for form in mention_forms):
            return

        now = time.time()
        if now - self._last_response.get(message.author.id, 0) < MENTION_COOLDOWN_SECONDS:
            return
        self._last_response[message.author.id] = now

        try:
            response, is_hostile = get_response(message.content)

            if is_hostile:
                key = f"hostile:{message.author.id}"
                count = int(await get_bot_state(key) or 0) + 1
                await set_bot_state(key, str(count))
                response = f"{response} (that's {count} strikes)"

            await message.reply(response, mention_author=False)
        except discord.HTTPException as e:
            log(f"[SENTIENCE] failed to reply in {message.channel}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(SentienceCog(bot))