import random
import discord
from discord.ext import commands
from bot.utils.storage import load_json, save_json

MARRIAGE_FILE = "marriages.json"
MARRIAGE_PROPOSALS: dict[str, str] = {}

def load_marriages(): return load_json(MARRIAGE_FILE, {})
def save_marriages(d): save_json(MARRIAGE_FILE, d)

class Social(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="marry", help="Propose to someone ❤️")
    async def marry(self, ctx, member: discord.Member):
        if member == ctx.author:
            return await ctx.send("❌ You can't marry yourself!")
        if member.bot:
            return await ctx.send("🤖 You can't marry a bot.")

        marriages = load_marriages()
        author_id = str(ctx.author.id)
        target_id = str(member.id)

        if marriages.get(author_id) or marriages.get(target_id):
            return await ctx.send("💔 One of you is already married.")

        if target_id in MARRIAGE_PROPOSALS:
            return await ctx.send("⏳ That person already has a pending proposal. Please wait.")

        MARRIAGE_PROPOSALS[target_id] = author_id
        await ctx.send(
            f"💍 {ctx.author.mention} has proposed to {member.mention}!\n"
            f"{member.mention}, type `!accept` to say yes!"
        )

    @commands.command(name="accept", help="Accept a marriage proposal 💖")
    async def accept(self, ctx):
        user_id = str(ctx.author.id)
        proposer_id = MARRIAGE_PROPOSALS.get(user_id)
        if not proposer_id:
            return await ctx.send("❌ You don't have any pending proposals.")

        marriages = load_marriages()
        if marriages.get(proposer_id) or marriages.get(user_id):
            MARRIAGE_PROPOSALS.pop(user_id, None)
            return await ctx.send("💔 One of you is already married.")

        marriages[proposer_id] = user_id
        marriages[user_id] = proposer_id
        save_marriages(marriages)

        proposer = await self.bot.fetch_user(int(proposer_id))
        await ctx.send(f"💞 {ctx.author.mention} and {proposer.mention} are now married! 🎉")
        del MARRIAGE_PROPOSALS[user_id]

    @commands.command(name="divorce", help="Divorce your current partner 😢")
    async def divorce(self, ctx):
        user_id = str(ctx.author.id)
        marriages = load_marriages()
        partner_id = marriages.get(user_id)
        if not partner_id:
            return await ctx.send("❌ You are not married.")

        marriages.pop(user_id, None)
        marriages.pop(partner_id, None)
        save_marriages(marriages)

        partner = await self.bot.fetch_user(int(partner_id))
        await ctx.send(f"💔 {ctx.author.mention} and {partner.mention} are now divorced.")

    @commands.command(name="partner", help="View your or someone else's partner 💘")
    async def partner(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        marriages = load_marriages()
        partner_id = marriages.get(str(member.id))
        if not partner_id:
            return await ctx.send(f"{member.display_name} is not married.")
        partner_user = await self.bot.fetch_user(int(partner_id))
        await ctx.send(f"💗 {member.display_name}'s partner is **{partner_user.display_name}**.")

    @commands.command(name="flirt", help="Flirt with someone using a cute compliment 😘")
    async def flirt(self, ctx, member: discord.Member):
        if member == ctx.author:
            return await ctx.send("😳 You can’t flirt with yourself... or can you?")
        if member.bot:
            return await ctx.send("🤖 Bots don't understand love... yet.")

        lines = [
            "Are you Wi-Fi? Because I’m feeling a strong connection.",
            "Do you have a map? I keep getting lost in your messages.",
            "If charm were XP, you'd be max level.",
            "You’re the reason the server’s uptime just improved.",
            "I’d share my last health potion with you. 💖",
        ]
        await ctx.send(f"{ctx.author.mention} flirts with {member.mention}:\n> {random.choice(lines)}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Social(bot))
