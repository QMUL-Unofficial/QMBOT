import discord
from discord.ext import commands
import aiohttp
import asyncio

from bot.config import (
    MC_NAME, MC_ADDRESS, MC_JAVA_PORT, MC_VERSION, MC_LOADER, MC_MODPACK_NAME,
    MC_WHITELISTED, MC_REGION, MC_NOTES,
    MC_MODRINTH_URL, MC_MAP_URL, MC_RULES_URL, MC_DISCORD_URL,
    MC_SHOW_BEDROCK, MC_BEDROCK_PORT
)

class MCLinksView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        if MC_MODRINTH_URL:
            self.add_item(discord.ui.Button(label="Modrinth", url=MC_MODRINTH_URL))
        if MC_MAP_URL:
            self.add_item(discord.ui.Button(label="Live Map", url=MC_MAP_URL))
        if MC_RULES_URL:
            self.add_item(discord.ui.Button(label="Rules", url=MC_RULES_URL))
        if MC_DISCORD_URL:
            self.add_item(discord.ui.Button(label="Discord", url=MC_DISCORD_URL))

async def fetch_mc_status_fallback(address: str):
    url = f"https://api.mcsrvstat.us/2/{address}"
    timeout = aiohttp.ClientTimeout(total=6)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Fallback API returned HTTP {resp.status}")
            return await resp.json()

class Minecraft(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="mc", help="Show Minecraft server info (IP, version, modpack, status, etc.)")
    async def mc(self, ctx: commands.Context):
        address = MC_ADDRESS

        desc_lines = [
            "**Join (Java):** `qmul-survival.modrinth.gg`",
            "",
            "**How to join:** Multiplayer → Add Server → paste the address above.",
        ]
        if MC_SHOW_BEDROCK:
            desc_lines += [
                "",
                f"**Bedrock Address:** `{address}`",
                f"**Bedrock Port:** `{MC_BEDROCK_PORT}`",
            ]

        embed = discord.Embed(
            title=f"⛏️ {MC_NAME} — Minecraft Server",
            description="\n".join(desc_lines),
            color=discord.Color.purple()
        )

        embed.add_field(name="Version", value=f"`{MC_VERSION}`", inline=True)
        embed.add_field(name="Loader", value=f"`{MC_LOADER}`", inline=True)
        embed.add_field(name="Modpack", value=f"`{MC_MODPACK_NAME}`", inline=True)
        embed.add_field(name="Access", value=("Whitelist ON" if MC_WHITELISTED else "Public / No whitelist"), inline=True)
        embed.add_field(name="Region", value=MC_REGION, inline=True)

        if MC_NOTES:
            embed.add_field(name="📌 Notes", value="\n".join(f"• {x}" for x in MC_NOTES)[:1024], inline=False)

        # Live status
        live_set = False
        try:
            from mcstatus import JavaServer

            def ping_java():
                if MC_JAVA_PORT:
                    server = JavaServer.lookup(f"{address}:{MC_JAVA_PORT}")
                else:
                    server = JavaServer.lookup(address)
                return server.status()

            status = await asyncio.to_thread(ping_java)
            online = getattr(status.players, "online", None)
            maxp = getattr(status.players, "max", None)

            if online is not None and maxp is not None:
                embed.add_field(name="🟢 Server Status", value=f"Online — **{online}/{maxp}** players", inline=False)
            else:
                embed.add_field(name="🟢 Server Status", value="Online", inline=False)
            live_set = True

        except Exception:
            pass

        if not live_set:
            try:
                data = await fetch_mc_status_fallback(address)
                if not data.get("online"):
                    embed.add_field(name="🔴 Server Status", value="Offline", inline=False)
                else:
                    players = data.get("players") or {}
                    embed.add_field(name="🟢 Server Status", value=f"Online — **{players.get('online','?')}/{players.get('max','?')}** players", inline=False)
            except Exception:
                embed.add_field(name="⚠️ Live Status", value="Couldn’t fetch status right now.", inline=False)

        embed.set_footer(text=f"Copy/paste Java join IP: {address}")
        await ctx.send(embed=embed, view=MCLinksView())

async def setup(bot: commands.Bot):
    await bot.add_cog(Minecraft(bot))
