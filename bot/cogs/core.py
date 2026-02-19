import discord
from discord.ext import commands

from bot.config import XP_PER_MESSAGE, TOP_ROLE_NAME, LEVEL_UP_CHANNEL_ID, EVENTS
from bot.utils.storage import load_json, save_json

DATA_FILE = "data.json"
EVENT_FILE = "events.json"

# Local copy of EVENTS like your original (keep in config if you want)
EVENTS = {
    "Double XP": {"xp_mult": 2},
    "Crash Week": {"crash_odds": 0.3},
    "Boom Frenzy": {"boom_odds": 0.3},
    "Coin Rain": {"bonus_daily": 100},
}

AFK_STATUS = {}  # key: f"{guild_id}-{user_id}" -> reason

def calculate_level(xp: int) -> int:
    return int(xp ** 0.5)

def load_data():
    return load_json(DATA_FILE, {})

def save_data(d):
    save_json(DATA_FILE, d)

def load_event():
    return load_json(EVENT_FILE, {})

def save_event(d):
    save_json(EVENT_FILE, d)

async def update_top_exp_role(guild: discord.Guild):
    data = load_data()
    gid = str(guild.id)
    if gid not in data or not data[gid]:
        return
    top_user_id, _ = max(data[gid].items(), key=lambda x: x[1].get("xp", 0))
    top_member = guild.get_member(int(top_user_id))
    if not top_member:
        return

    role = discord.utils.get(guild.roles, name=TOP_ROLE_NAME)
    if not role:
        try:
            role = await guild.create_role(name=TOP_ROLE_NAME)
        except discord.Forbidden:
            return

    for m in guild.members:
        if role in m.roles and m != top_member:
            await m.remove_roles(role)
    if role not in top_member.roles:
        await top_member.add_roles(role)

async def update_xp(bot: commands.Bot, user_id: int, guild_id: int, xp_amount: int):
    data = load_data()
    gid = str(guild_id)
    uid = str(user_id)

    data.setdefault(gid, {})
    user = data[gid].setdefault(uid, {"xp": 0})

    prev_xp = int(user.get("xp", 0))
    prev_level = int(user.get("level", calculate_level(prev_xp)))

    event = load_event()
    mult = EVENTS.get(event.get("active", ""), {}).get("xp_mult", 1)

    user["xp"] = prev_xp + int(xp_amount * mult)
    new_level = calculate_level(int(user["xp"]))
    user["level"] = new_level

    save_data(data)

    # Level-up announcements (your logic)
    if new_level > prev_level and new_level % 5 == 0:
        ch = bot.get_channel(LEVEL_UP_CHANNEL_ID)
        if ch:
            u = await bot.fetch_user(user_id)
            await ch.send(f"🎉 **{u.mention}** just reached level **{new_level}**! 🚀")

    # Optional role per 10 levels (kept)
    if new_level % 10 == 0:
        role_name = f"Level {new_level}"
        guild = bot.get_guild(int(gid))
        if guild:
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                try:
                    role = await guild.create_role(name=role_name)
                except discord.Forbidden:
                    role = None
            member = guild.get_member(int(uid))
            if role and member:
                await member.add_roles(role)

    guild = bot.get_guild(int(gid))
    if guild:
        await update_top_exp_role(guild)

class Core(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="afk", help="Set your AFK status with a reason")
    async def afk(self, ctx, *, reason: str = "AFK"):
        key = f"{ctx.guild.id}-{ctx.author.id}"
        AFK_STATUS[key] = reason
        embed = discord.Embed(description=f"{ctx.author.mention} is now AFK: {reason}", color=discord.Color.green())
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Word filter example (your original)
        if message.guild and "pathical" in message.content.lower():
            try:
                await message.delete()
            except discord.Forbidden:
                pass
            await message.channel.send(f"{message.author.mention} stop being a bum 😭", delete_after=5)
            return

        if message.guild:
            # clear AFK on speaking
            key = f"{message.guild.id}-{message.author.id}"
            if key in AFK_STATUS:
                del AFK_STATUS[key]
                await message.channel.send(embed=discord.Embed(
                    description=f"{message.author.mention} is no longer AFK.",
                    color=discord.Color.red()
                ))

            # announce AFK if someone is mentioned
            for user in message.mentions:
                mention_key = f"{message.guild.id}-{user.id}"
                if mention_key in AFK_STATUS:
                    reason = AFK_STATUS[mention_key]
                    await message.channel.send(embed=discord.Embed(
                        description=f"{user.display_name} is currently AFK: {reason}",
                        color=discord.Color.purple()
                    ))

            # XP
            try:
                await update_xp(self.bot, message.author.id, message.guild.id, XP_PER_MESSAGE)
            except Exception as e:
                print(f"[XP] update_xp failed: {type(e).__name__}: {e}")

        await self.bot.process_commands(message)

async def setup(bot: commands.Bot):
    await bot.add_cog(Core(bot))
