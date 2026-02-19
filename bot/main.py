import os
import asyncio
from dotenv import load_dotenv

from .client import bot

COGS = [
    "bot.cogs.core",
    "bot.cogs.economy",
    "bot.cogs.stocks",
    "bot.cogs.trivia",
    "bot.cogs.games_blackjack",
    "bot.cogs.games_snake",
    "bot.cogs.ramadan",
    "bot.cogs.minecraft",
    "bot.cogs.social",
    "bot.cogs.moderation",
    "bot.cogs.admin",
]

async def _load_cogs():
    for ext in COGS:
        try:
            await bot.load_extension(ext)
            print(f"[Cog] LOADED {ext}")
        except Exception as e:
            print(f"[Cog] FAILED {ext}: {type(e).__name__}: {e}")

def main():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not set in Railway Variables")

    async def runner():
        await _load_cogs()
        await bot.start(token)

    asyncio.run(runner())
