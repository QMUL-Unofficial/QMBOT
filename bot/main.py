import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "bot.cogs.core",
    "bot.cogs.economy",
    "bot.cogs.stocks",
    "bot.cogs.trivia",
    "bot.cogs.games_blackjack",
    "bot.cogs.games_snake",
    "bot.cogs.minecraft",
    "bot.cogs.ramadan",
    "bot.cogs.social",
    "bot.cogs.moderation",
    "bot.cogs.admin",
]


async def load_cogs():
    for ext in COGS:
        try:
            await bot.load_extension(ext)
            print(f"[Cog] Loaded {ext}")
        except Exception as e:
            print(f"[Cog] FAILED {ext}: {type(e).__name__}: {e}")


async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN not set in environment.")
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
