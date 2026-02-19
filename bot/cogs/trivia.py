import random
import asyncio
import discord
import aiohttp
from discord.ext import commands

from bot.utils.storage import load_json, save_json
from bot.cogs.core import update_xp
from bot.cogs.economy import ensure_user_coins, load_coins, save_coins

TRIVIA_STATS_FILE = "trivia_stats.json"
TRIVIA_STREAKS_FILE = "trivia_streaks.json"

def load_trivia_stats(): return load_json(TRIVIA_STATS_FILE, {})
def save_trivia_stats(d): save_json(TRIVIA_STATS_FILE, d)

def load_trivia_streaks(): return load_json(TRIVIA_STREAKS_FILE, {})
def save_trivia_streaks(d): save_json(TRIVIA_STREAKS_FILE, d)

def add_trivia_result(uid: str, category: str, correct: bool):
    stats = load_trivia_stats()
    user = stats.setdefault(uid, {})
    cat = user.setdefault(category, {"correct": 0, "attempts": 0})
    cat["attempts"] += 1
    if correct:
        cat["correct"] += 1
    save_trivia_stats(stats)

class Trivia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="trivia", help="Answer a trivia question with emoji reactions!")
    async def trivia(self, ctx):
        url = "https://the-trivia-api.com/v2/questions"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return await ctx.send("❌ Could not reach Trivia API. Try again later.")
                data = await resp.json()

        if not data:
            return await ctx.send("❌ No trivia received.")

        q = data[0]
        question = q["question"]["text"]
        correct = q["correctAnswer"]
        options = q["incorrectAnswers"] + [correct]
        random.shuffle(options)

        raw_cat = q.get("category", "General")
        category = (raw_cat[0] if isinstance(raw_cat, list) and raw_cat else raw_cat)
        category = str(category).title()

        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        option_lines = "\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options))

        embed = discord.Embed(
            title="🧠 Trivia Time!",
            description=f"**{question}**\n\n{option_lines}\n\nReact with the correct answer!",
            color=discord.Color.blue()
        )
        msg = await ctx.send(embed=embed)
        for emoji in emojis:
            await msg.add_reaction(emoji)

        def check(payload: discord.RawReactionActionEvent):
            return (
                payload.user_id == ctx.author.id and
                payload.message_id == msg.id and
                str(payload.emoji) in emojis
            )

        try:
            payload = await self.bot.wait_for("raw_reaction_add", timeout=20.0, check=check)
        except asyncio.TimeoutError:
            return await ctx.send(f"⏰ Out of time! The correct answer was **{correct}**.")

        chosen = options[emojis.index(str(payload.emoji))]
        uid = str(ctx.author.id)
        streaks = load_trivia_streaks()
        streak = int(streaks.get(uid, 0))

        if chosen == correct:
            streak += 1
            reward_base = 50
            streak_bonus = 5 * min(streak - 1, 10)
            reward = reward_base + streak_bonus

            ensure_user_coins(ctx.author.id)
            coins = load_coins()
            coins[uid]["wallet"] += reward
            save_coins(coins)

            await update_xp(self.bot, ctx.author.id, ctx.guild.id, 20)

            add_trivia_result(uid, category, True)
            streaks[uid] = streak
            save_trivia_streaks(streaks)

            await ctx.send(f"✅ Correct! **+{reward}** coins (streak **{streak}**).")
        else:
            add_trivia_result(uid, category, False)
            streaks[uid] = 0
            save_trivia_streaks(streaks)
            await ctx.send(f"❌ Wrong! The correct answer was **{correct}**. Streak reset.")

    @commands.command(name="triviastats", help="Show trivia stats. Usage: !triviastats [@user]")
    async def triviastats(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        uid = str(member.id)
        stats = load_trivia_stats()
        u = stats.get(uid)

        if not u:
            return await ctx.send(f"📊 No trivia stats for **{member.display_name}** yet.")

        rows = []
        total_attempts = 0
        total_correct = 0
        for cat, rec in u.items():
            attempts = int(rec.get("attempts", 0))
            correct = int(rec.get("correct", 0))
            wrong = attempts - correct
            acc = (correct / attempts * 100.0) if attempts else 0.0
            total_attempts += attempts
            total_correct += correct
            rows.append((cat, correct, wrong, attempts, acc))

        rows.sort(key=lambda r: r[3], reverse=True)

        lines = []
        for cat, correct, wrong, attempts, acc in rows[:20]:
            lines.append(f"**{cat}** — ✅ {correct} · ❌ {wrong} · {attempts} total · {acc:.0f}%")

        overall_acc = (total_correct / total_attempts * 100.0) if total_attempts else 0.0
        embed = discord.Embed(
            title=f"📊 Trivia Stats — {member.display_name}",
            description="\n".join(lines),
            color=discord.Color.teal()
        )
        embed.set_footer(text=f"Overall: ✅ {total_correct} / {total_attempts} · {overall_acc:.0f}% accuracy")
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))
