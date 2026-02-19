import discord
from discord.ext import commands

def build_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True
    intents.members = True

    return commands.Bot(command_prefix="!", intents=intents)

bot = build_bot()
