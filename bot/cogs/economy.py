# bot/cogs/economy.py
import time
import random
import discord
from discord.ext import commands, tasks

from bot.config import (
    STOCKS,
    SHOP_ITEMS,
    ITEM_PRICES,
    CRASH_TOKEN_NAME,
    ALWAYS_BANKROB_USER_ID,
    BANKROB_STEAL_MIN_PCT,
    BANKROB_STEAL_MAX_PCT,
    BANKROB_MIN_STEAL,
    BANKROB_MAX_STEAL_PCT_CAP,
    MARKET_ANNOUNCE_CHANNEL_ID,
    SUGGESTION_CHANNEL_ID,
)

from bot.utils.storage import load_json, save_json
from bot.utils.locks import MONEY_LOCKS
from bot.utils.members import get_member_safe

# If you want shop auto-restock every 5 minutes
SHOP_RESTOCK_CHECK_MINUTES = 5
SHOP_RESTOCK_CHANCE = 0.12        # 12% chance per item per check
SHOP_RESTOCK_MAX_ADD = 2          # adds 1..2 when it restocks

# Cooldowns (seconds)
DAILY_RESET_MODE = "utc_midnight"  # keep as-is
BEG_COOLDOWN = 30
ROB_COOLDOWN = 300
BANKROB_COOLDOWN = 600

# JSON files
COIN_DATA_FILE = "coins.json"
INVENTORY_FILE = "inventories.json"
SHOP_FILE = "shop_stock.json"
SUGGESTION_FILE = "suggestions.json"
BEG_STATS_FILE = "beg_stats.json"


# -----------------------
# Storage helpers
# -----------------------
def load_coins():
    return load_json(COIN_DATA_FILE, {})


def save_coins(d):
    save_json(COIN_DATA_FILE, d)


def load_inventory():
    return load_json(INVENTORY_FILE, {})


def save_inventory(d):
    save_json(INVENTORY_FILE, d)


def load_shop_stock():
    stock = load_json(SHOP_FILE, None)
    if stock is None:
        stock = {item: 0 for item in SHOP_ITEMS}
        save_shop_stock(stock)
        return stock
    # ensure keys exist
    changed = False
    for item in SHOP_ITEMS:
        if item not in stock:
            stock[item] = 0
            changed = True
    if changed:
        save_shop_stock(stock)
    return stock


def save_shop_stock(d):
    save_json(SHOP_FILE, d)


def load_suggestions():
    return load_json(SUGGESTION_FILE, [])


def save_suggestions(d):
    save_json(SUGGESTION_FILE, d)


def load_beg_stats():
    return load_json(BEG_STATS_FILE, {})


def save_beg_stats(d):
    save_json(BEG_STATS_FILE, d)


def ensure_user_coins(user_id: int | str):
    uid = str(user_id)
    coins = load_coins()

    if uid not in coins:
        coins[uid] = {
            "wallet": 100,
            "bank": 0,
            "last_daily": 0.0,
            "last_rob": 0.0,
            "last_bankrob": 0.0,
            "last_beg": 0.0,
            "portfolio": {s: 0 for s in STOCKS},
        }
        save_coins(coins)
        return coins

    data = coins[uid]
    changed = False
    for k, default in [
        ("wallet", 100),
        ("bank", 0),
        ("last_daily", 0.0),
        ("last_rob", 0.0),
        ("last_bankrob", 0.0),
        ("last_beg", 0.0),
    ]:
        if k not in data:
            data[k] = default
            changed = True

    if "portfolio" not in data or not isinstance(data["portfolio"], dict):
        data["portfolio"] = {s: 0 for s in STOCKS}
        changed = True
    else:
        for s in STOCKS:
            if s not in data["portfolio"]:
                data["portfolio"][s] = 0
                changed = True

    if changed:
        save_coins(coins)
    return coins


def ensure_user_inventory(user_id: int | str):
    uid = str(user_id)
    inv = load_inventory()
    if uid not in inv:
        inv[uid] = {}
        save_inventory(inv)
    return inv


def _match_item(name: str) -> str | None:
    """Case-insensitive match to a SHOP_ITEMS entry."""
    n = name.strip().lower()
    for item in SHOP_ITEMS:
        if item.lower() == n:
            return item
    # allow partial-ish matches (careful)
    for item in SHOP_ITEMS:
        if n == item.lower().replace("'", ""):
            return item
    return None


def _match_stock(name: str) -> str | None:
    n = name.strip().lower()
    for s in STOCKS:
        if s.lower() == n:
            return s
    return None


def _parse_item_and_qty(raw: str) -> tuple[str, int]:
    """
    Accept:
      - '!buy Anime body pillow'
      - '!buy Anime body pillow 2'
      - '!buy 2 Anime body pillow'
    Returns (item_string, qty)
    """
    parts = raw.strip().split()
    if not parts:
        return "", 1

    # qty first
    if parts[0].isdigit():
        qty = max(1, int(parts[0]))
        item = " ".join(parts[1:]).strip()
        return item, qty

    # qty last
    if parts[-1].isdigit():
        qty = max(1, int(parts[-1]))
        item = " ".join(parts[:-1]).strip()
        return item, qty

    return raw.strip(), 1


def _only_mention_target(ctx) -> int | None:
    if len(ctx.message.mentions) != 1:
        return None
    return ctx.message.mentions[0].id


def _format_coins(n: int) -> str:
    return f"{int(n):,}"


# -----------------------
# Trade state (simple)
# -----------------------
# key: target_user_id -> proposal dict
TRADE_PROPOSALS: dict[str, dict] = {}


# -----------------------
# Cog
# -----------------------
class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.shop_restock_loop.start()

    def cog_unload(self):
        self.shop_restock_loop.cancel()

    # ---------- Suggestions ----------
    @commands.command(name="suggest", help="Submit a suggestion to the server.")
    async def suggest(self, ctx, *, message: str):
        suggestions = load_suggestions()
        suggestions.append(
            {
                "user_id": ctx.author.id,
                "username": ctx.author.name,
                "suggestion": message,
                "timestamp": discord.utils.utcnow().isoformat(),
            }
        )
        save_suggestions(suggestions)

        channel = self.bot.get_channel(SUGGESTION_CHANNEL_ID)
        if not channel:
            return await ctx.send("❌ Suggestion channel not found. Please contact an admin.")

        embed = discord.Embed(title="📬 New Suggestion", description=message, color=discord.Color.teal())
        embed.set_footer(text=f"Suggested by {ctx.author.display_name}")
        msg = await channel.send(embed=embed)
        try:
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
        except Exception:
            pass

        await ctx.send("✅ Your suggestion has been submitted!")

    # ---------- Balance / bank ----------
    @commands.command(name="balance", aliases=["bal"], help="Check your or someone else's wallet and bank balance.")
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        ensure_user_coins(member.id)
        coins = load_coins()
        data = coins[str(member.id)]

        embed = discord.Embed(title=f"💰 {member.display_name}'s Balance", color=discord.Color.purple())
        embed.add_field(name="Wallet", value=f"💵 {_format_coins(data['wallet'])} coins", inline=True)
        embed.add_field(name="Bank", value=f"🏦 {_format_coins(data['bank'])} coins", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="deposit", aliases=["dep"], help="Deposit to bank. Usage: !deposit <amount> or !deposit all")
    async def deposit(self, ctx, amount: str):
        uid = str(ctx.author.id)
        ensure_user_coins(uid)
        coins = load_coins()
        data = coins[uid]

        if amount.lower() == "all":
            amt = int(data["wallet"])
        else:
            if not amount.isdigit():
                return await ctx.send(embed=discord.Embed(description="❌ Enter a number or `all`.", color=discord.Color.orange()))
            amt = int(amount)

        if amt <= 0 or amt > int(data["wallet"]):
            return await ctx.send(embed=discord.Embed(description="❌ Not enough wallet balance.", color=discord.Color.orange()))

        data["wallet"] -= amt
        data["bank"] += amt
        save_coins(coins)

        await ctx.send(embed=discord.Embed(description=f"🏦 Deposited **{_format_coins(amt)}** coins.", color=discord.Color.orange()))

    @commands.command(name="withdraw", aliases=["with"], help="Withdraw from bank. Usage: !withdraw <amount> or !withdraw all")
    async def withdraw(self, ctx, amount: str):
        uid = str(ctx.author.id)
        ensure_user_coins(uid)
        coins = load_coins()
        data = coins[uid]

        if amount.lower() == "all":
            amt = int(data["bank"])
        else:
            if not amount.isdigit():
                return await ctx.send(embed=discord.Embed(description="❌ Enter a number or `all`.", color=discord.Color.orange()))
            amt = int(amount)

        if amt <= 0 or amt > int(data["bank"]):
            return await ctx.send(embed=discord.Embed(description="❌ Not enough bank balance.", color=discord.Color.orange()))

        data["bank"] -= amt
        data["wallet"] += amt
        save_coins(coins)

        await ctx.send(embed=discord.Embed(description=f"💰 Withdrew **{_format_coins(amt)}** coins.", color=discord.Color.orange()))

    # ---------- Pay / donate ----------
    @commands.command(name="pay", help="Send coins to another user. Usage: !pay @user <amount>")
    async def pay(self, ctx, member: discord.Member, amount: int):
        if member == ctx.author:
            return await ctx.send("❌ You can't pay yourself.")
        if member.bot:
            return await ctx.send("🤖 You can't pay bots.")
        if amount <= 0:
            return await ctx.send("❌ Enter an amount > 0.")

        a = ctx.author.id
        b = member.id
        first, second = sorted([a, b])

        async with MONEY_LOCKS[first], MONEY_LOCKS[second]:
            ensure_user_coins(a)
            ensure_user_coins(b)
            coins = load_coins()

            sender = coins[str(a)]
            recipient = coins[str(b)]

            if int(sender["wallet"]) < amount:
                return await ctx.send("💸 You don't have enough coins in your wallet.")

            sender["wallet"] -= amount
            recipient["wallet"] += amount
            save_coins(coins)

        await ctx.send(embed=discord.Embed(description=f"✅ Sent **{_format_coins(amount)}** coins to {member.mention}!", color=discord.Color.green()))

    @commands.command(name="donate", help="Donate coins to someone. Usage: !donate @user <amount>")
    async def donate(self, ctx, member: discord.Member, amount: int):
        if member == ctx.author:
            return await ctx.send(embed=discord.Embed(description="❌ You can't donate to yourself.", color=discord.Color.orange()))
        if member.bot:
            return await ctx.send(embed=discord.Embed(description="🤖 Bots don't need donations.", color=discord.Color.orange()))
        if amount <= 0:
            return await ctx.send(embed=discord.Embed(description="❌ Amount must be > 0.", color=discord.Color.orange()))

        a = ctx.author.id
        b = member.id
        first, second = sorted([a, b])

        async with MONEY_LOCKS[first], MONEY_LOCKS[second]:
            ensure_user_coins(a)
            ensure_user_coins(b)
            coins = load_coins()

            donor = coins[str(a)]
            recipient = coins[str(b)]

            if int(donor["wallet"]) < amount:
                return await ctx.send(embed=discord.Embed(description="💸 Not enough wallet balance.", color=discord.Color.orange()))

            donor["wallet"] -= amount
            recipient["wallet"] += amount
            save_coins(coins)

        await ctx.send(embed=discord.Embed(description=f"💖 {ctx.author.mention} donated **{_format_coins(amount)}** coins to {member.mention}!", color=discord.Color.orange()))

    # ---------- Daily ----------
    @commands.command(name="daily", help="Claim your daily reward (resets at midnight UTC).")
    async def daily(self, ctx):
        uid = str(ctx.author.id)
        ensure_user_coins(uid)
        coins = load_coins()
        data = coins[uid]

        now = discord.utils.utcnow()
        last_ts = float(data.get("last_daily", 0.0))
        last_dt = discord.utils.utcnow().fromtimestamp(last_ts) if last_ts else None

        if last_dt and last_dt.date() == now.date():
            tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0) + discord.utils.timedelta(days=1)
            remaining = int((tomorrow - now).total_seconds())
            h = remaining // 3600
            m = (remaining % 3600) // 60
            s = remaining % 60
            return await ctx.send(
                embed=discord.Embed(
                    description=f"🕒 Already claimed. Try again in **{h}h {m}m {s}s** (midnight UTC).",
                    color=discord.Color.purple(),
                )
            )

        reward = random.randint(200, 350)
        data["wallet"] += reward
        data["last_daily"] = now.timestamp()
        save_coins(coins)

        await ctx.send(embed=discord.Embed(description=f"💰 Daily claimed: **{_format_coins(reward)}** coins!", color=discord.Color.purple()))

    # ---------- Beg ----------
    @commands.command(name="beg", help="Beg for coins (has cooldown, levels up over time).")
    async def beg(self, ctx):
        uid = str(ctx.author.id)

        ensure_user_coins(uid)
        coins = load_coins()
        data = coins[uid]

        now = time.time()
        last_beg = float(data.get("last_beg", 0.0))
        if now - last_beg < BEG_COOLDOWN:
            remaining = int(BEG_COOLDOWN - (now - last_beg))
            return await ctx.send(f"⏳ Wait **{remaining}s** before begging again.")

        beg_stats = load_beg_stats()
        user_beg = beg_stats.setdefault(uid, {"xp": 0, "level": 1, "total_begs": 0})

        # level curve (same “sqrt-ish” vibe as your original)
        user_beg["level"] = int((int(user_beg["xp"]) ** 0.5) // 5 + 1)

        base_min = 10 + user_beg["level"] * 2
        base_max = 30 + user_beg["level"] * 5
        amount = random.randint(base_min, base_max)

        data["wallet"] += amount
        data["last_beg"] = now

        xp_gain = random.randint(5, 12)
        user_beg["xp"] += xp_gain
        user_beg["total_begs"] += 1

        save_coins(coins)
        save_beg_stats(beg_stats)

        embed = discord.Embed(
            title="🙏 Successful Beg",
            description=(
                f"You received **{_format_coins(amount)}** coins!\n\n"
                f"📈 Beg Level: **{user_beg['level']}** | Total Begs: **{user_beg['total_begs']}**\n"
                f"✨ XP Gained: **+{xp_gain}**"
            ),
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="begleaderboard", aliases=["begtop"], help="Show top beggars in the server.")
    async def begleaderboard(self, ctx, count: int = 10):
        count = max(3, min(25, int(count)))
        beg_stats = load_beg_stats()

        entries = []
        for member in ctx.guild.members:
            if member.bot:
                continue
            stats = beg_stats.get(str(member.id))
            if not stats:
                continue
            level = int(stats.get("level", 1))
            xp = int(stats.get("xp", 0))
            begs = int(stats.get("total_begs", 0))
            entries.append((member, level, xp, begs))

        if not entries:
            return await ctx.send("📭 No begging data yet.")

        entries.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)

        lines = []
        for i, (member, level, xp, begs) in enumerate(entries[:count], start=1):
            crown = " 👑" if i == 1 else ""
            you = " ← you" if member.id == ctx.author.id else ""
            lines.append(f"**{i}.** {member.mention}{crown} — Lvl **{level}** · {xp} XP · {begs} begs{you}")

        embed = discord.Embed(title="🏆 Begging Leaderboard", description="\n".join(lines), color=discord.Color.gold())
        await ctx.send(embed=embed)

    # ---------- Rob ----------
    @commands.command(name="rob", help="Attempt to rob someone. Usage: !rob @user")
    async def rob(self, ctx):
        target_id = _only_mention_target(ctx)
        if target_id is None:
            return await ctx.send("❌ Please mention exactly one user: `!rob @user`")
        if target_id == ctx.author.id:
            return await ctx.send(embed=discord.Embed(description="❌ You can't rob yourself.", color=discord.Color.purple()))

        target_member = ctx.guild.get_member(target_id) or await get_member_safe(ctx.guild, target_id)
        if not target_member:
            return await ctx.send("❌ Could not find that member in this server.")
        if target_member.bot:
            return await ctx.send(embed=discord.Embed(description="🤖 You can't rob bots.", color=discord.Color.purple()))

        a = ctx.author.id
        b = target_id
        first, second = sorted([a, b])

        async with MONEY_LOCKS[first], MONEY_LOCKS[second]:
            ensure_user_coins(a)
            ensure_user_coins(b)
            coins = load_coins()

            thief = coins[str(a)]
            victim = coins[str(b)]

            now = time.time()
            if now - float(thief.get("last_rob", 0.0)) < ROB_COOLDOWN:
                remaining = int(ROB_COOLDOWN - (now - float(thief.get("last_rob", 0.0))))
                return await ctx.send(embed=discord.Embed(description=f"⏳ Cooldown: **{remaining}**s", color=discord.Color.purple()))

            if int(victim.get("wallet", 0)) < 50:
                return await ctx.send(embed=discord.Embed(description="😒 That user doesn't have enough in wallet to rob.", color=discord.Color.purple()))

            stolen = random.randint(10, max(10, int(victim["wallet"]) // 2))
            victim["wallet"] -= stolen
            thief["wallet"] += stolen
            thief["last_rob"] = now

            save_coins(coins)

        await ctx.send(embed=discord.Embed(
            description=f"💸 You robbed **{target_member.display_name}** and got **{_format_coins(stolen)}** coins!",
            color=discord.Color.purple()
        ))

    # ---------- Bankrob ----------
    @commands.command(name="bankrob", help="Rob a specific person's bank (risky!). Usage: !bankrob @user")
    async def bankrob(self, ctx):
        target_id = _only_mention_target(ctx)
        if target_id is None:
            return await ctx.send("❌ Usage: `!bankrob @user` (mention exactly one person)")
        if target_id == ctx.author.id:
            return await ctx.send(embed=discord.Embed(description="❌ You can’t rob yourself.", color=discord.Color.purple()))

        member = ctx.guild.get_member(target_id) or await get_member_safe(ctx.guild, target_id)
        if not member:
            return await ctx.send("❌ Couldn’t find that member.")
        if member.bot:
            return await ctx.send(embed=discord.Embed(description="🤖 You can’t rob bots.", color=discord.Color.purple()))

        robber_id = ctx.author.id
        victim_id = target_id

        a, b = sorted([robber_id, victim_id])
        async with MONEY_LOCKS[a], MONEY_LOCKS[b]:
            ensure_user_coins(robber_id)
            ensure_user_coins(victim_id)
            coins = load_coins()
            robber = coins[str(robber_id)]
            victim = coins[str(victim_id)]

            now = time.time()
            if now - float(robber.get("last_bankrob", 0.0)) < BANKROB_COOLDOWN:
                remaining = int(BANKROB_COOLDOWN - (now - float(robber.get("last_bankrob", 0.0))))
                return await ctx.send(embed=discord.Embed(
                    description=f"🚨 Try again in **{remaining//60}m {remaining%60}s**.",
                    color=discord.Color.purple()
                ))

            robber["last_bankrob"] = now

            victim_bank = int(victim.get("bank", 0))
            if victim_bank < 100:
                save_coins(coins)
                return await ctx.send(embed=discord.Embed(
                    description=f"😓 {member.display_name} doesn’t have enough in the bank to rob.",
                    color=discord.Color.purple()
                ))

            if robber_id == ALWAYS_BANKROB_USER_ID:
                success = True
            else:
                success = random.choices([True, False], weights=[20, 80])[0]

            if success:
                pct = random.uniform(BANKROB_STEAL_MIN_PCT, BANKROB_STEAL_MAX_PCT)
                raw_amount = int(victim_bank * pct)
                hard_cap = int(victim_bank * BANKROB_MAX_STEAL_PCT_CAP)

                amount = max(BANKROB_MIN_STEAL, min(raw_amount, hard_cap, victim_bank))

                victim["bank"] -= amount
                robber["wallet"] += amount
                save_coins(coins)

                pct_display = (amount / max(1, victim_bank)) * 100
                return await ctx.send(embed=discord.Embed(
                    description=f"🏦 Success! You stole **{_format_coins(amount)}** coins from **{member.display_name}** (~{pct_display:.0f}% of their bank).",
                    color=discord.Color.purple()
                ))
            else:
                # fine
                fine_msg = "🚔 You got caught!"
                wallet = int(robber.get("wallet", 0))
                if wallet < 50:
                    fine_msg += " You were too broke to fine. Warning issued."
                else:
                    fine = random.randint(50, int(min(wallet, 150)))
                    robber["wallet"] -= fine
                    fine_msg += f" You lost **{_format_coins(fine)}** coins in legal fees."

                save_coins(coins)
                return await ctx.send(embed=discord.Embed(description=fine_msg, color=discord.Color.purple()))

    # ---------- Leaderboards ----------
    @commands.command(name="baltop", aliases=["rich", "leaderboard"], help="Top balances by wallet+bank for this server.")
    async def baltop(self, ctx, count: int = 10):
        count = max(3, min(25, int(count)))
        coins = load_coins()

        rows = []
        for m in ctx.guild.members:
            if m.bot:
                continue
            u = coins.get(str(m.id))
            if not u:
                continue
            total = int(u.get("wallet", 0)) + int(u.get("bank", 0))
            rows.append((m, total, int(u.get("wallet", 0)), int(u.get("bank", 0))))

        if not rows:
            return await ctx.send("📭 No economy data yet.")

        rows.sort(key=lambda r: r[1], reverse=True)

        lines = []
        for i, (m, total, w, b) in enumerate(rows[:count], start=1):
            crown = " 👑" if i == 1 else ""
            you = " ← you" if m.id == ctx.author.id else ""
            lines.append(f"**{i}.** {m.mention}{crown} — **{_format_coins(total)}** (w {_format_coins(w)} / b {_format_coins(b)}){you}")

        embed = discord.Embed(title="🏦 Baltop (Wallet + Bank)", description="\n".join(lines), color=discord.Color.gold())
        await ctx.send(embed=embed)

    @commands.command(name="networth", help="Shows your net worth including stocks.")
    async def networth(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        ensure_user_coins(member.id)
        coins = load_coins()
        u = coins[str(member.id)]

        wallet = int(u.get("wallet", 0))
        bank = int(u.get("bank", 0))

        # stock value via stocks.json (owned in portfolio)
        stocks_data = load_json("stocks.json", {})
        pf = u.get("portfolio", {}) or {}
        stock_value = 0
        for s in STOCKS:
            shares = int(pf.get(s, 0))
            price = int((stocks_data.get(s, {}) or {}).get("price", 0))
            stock_value += shares * price

        total = wallet + bank + stock_value
        embed = discord.Embed(title=f"📊 Net Worth — {member.display_name}", color=discord.Color.teal())
        embed.add_field(name="Wallet", value=_format_coins(wallet), inline=True)
        embed.add_field(name="Bank", value=_format_coins(bank), inline=True)
        embed.add_field(name="Stocks", value=_format_coins(stock_value), inline=True)
        embed.add_field(name="Total", value=f"**{_format_coins(total)}**", inline=False)
        await ctx.send(embed=embed)

    # ---------- Shop / inventory ----------
    @commands.command(name="shop", help="Browse items currently in stock.")
    async def shop(self, ctx):
        stock = load_shop_stock()
        embed = discord.Embed(title="🛒 QMUL Shop", color=discord.Color.purple())
        for item in SHOP_ITEMS:
            price = ITEM_PRICES.get(item, 0)
            count = int(stock.get(item, 0))
            embed.add_field(name=item, value=f"💰 { _format_coins(price) } coins\n📦 Stock: {count}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="buy", help="Buy an item. Usage: !buy <item> [qty] OR !buy <qty> <item>")
    async def buy(self, ctx, *, raw: str):
        item_str, qty = _parse_item_and_qty(raw)
        item = _match_item(item_str)
        if not item:
            return await ctx.send(f"❌ Item not found. Use `!shop` to see items.\nYou typed: `{item_str}`")

        if qty <= 0:
            return await ctx.send("❌ Quantity must be at least 1.")

        price = int(ITEM_PRICES.get(item, 0))
        if price <= 0:
            return await ctx.send("❌ This item can’t be purchased right now (price missing).")

        uid = ctx.author.id

        async with MONEY_LOCKS[uid]:
            ensure_user_coins(uid)
            ensure_user_inventory(uid)

            coins = load_coins()
            inv = load_inventory()
            shop = load_shop_stock()

            if int(shop.get(item, 0)) < qty:
                return await ctx.send(embed=discord.Embed(
                    description=f"📦 Not enough stock for **{item}**. Available: **{int(shop.get(item,0))}**",
                    color=discord.Color.orange()
                ))

            cost = price * qty
            if int(coins[str(uid)]["wallet"]) < cost:
                return await ctx.send(embed=discord.Embed(
                    description=f"💸 You need **{_format_coins(cost)}** coins in your wallet to buy that.",
                    color=discord.Color.orange()
                ))

            coins[str(uid)]["wallet"] -= cost
            shop[item] -= qty
            inv.setdefault(str(uid), {})
            inv[str(uid)][item] = int(inv[str(uid)].get(item, 0)) + qty

            save_coins(coins)
            save_shop_stock(shop)
            save_inventory(inv)

        await ctx.send(embed=discord.Embed(
            description=f"✅ Bought **{qty}× {item}** for **{_format_coins(cost)}** coins.",
            color=discord.Color.green()
        ))

    @commands.command(name="inventory", aliases=["inv"], help="View your or someone else's inventory.")
    async def inventory(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        ensure_user_inventory(member.id)
        inv = load_inventory()
        user_inv = inv.get(str(member.id), {}) or {}

        if not user_inv:
            return await ctx.send(embed=discord.Embed(
                description=f"{member.display_name} has nothing in their inventory 🪫",
                color=discord.Color.orange(),
            ))

        lines = []
        for item, qty in sorted(user_inv.items(), key=lambda x: (-int(x[1]), x[0].lower())):
            lines.append(f"• **{item}** — {int(qty)}")

        embed = discord.Embed(title=f"🎒 {member.display_name}'s Inventory", description="\n".join(lines)[:4000], color=discord.Color.orange())
        await ctx.send(embed=embed)

    # ---------- Trading (simple propose/accept) ----------
    @commands.command(name="trade", help="Propose a trade. Usage: !trade @user | give:<item> | want:<item>")
    async def trade(self, ctx, member: discord.Member, *, details: str):
        if member.bot or member.id == ctx.author.id:
            return await ctx.send("❌ Invalid trade target.")

        # parse "give:" and "want:"
        text = details.strip()
        give = ""
        want = ""
        for chunk in text.split("|"):
            c = chunk.strip()
            if c.lower().startswith("give:"):
                give = c[5:].strip()
            elif c.lower().startswith("want:"):
                want = c[5:].strip()

        if not give or not want:
            return await ctx.send("❌ Usage: `!trade @user | give:<item> | want:<item>`")

        give_item = _match_item(give) or give.strip()
        want_item = _match_item(want) or want.strip()

        ensure_user_inventory(ctx.author.id)
        inv = load_inventory()
        mine = inv.get(str(ctx.author.id), {}) or {}

        if int(mine.get(give_item, 0)) <= 0:
            return await ctx.send(f"❌ You don’t have **{give_item}** to offer.")

        TRADE_PROPOSALS[str(member.id)] = {
            "from": ctx.author.id,
            "to": member.id,
            "give": give_item,
            "want": want_item,
            "ts": time.time(),
            "guild_id": ctx.guild.id if ctx.guild else None,
        }

        await ctx.send(
            f"🤝 Trade proposed to {member.mention}!\n"
            f"**You give:** {give_item}\n"
            f"**You want:** {want_item}\n\n"
            f"{member.mention} can accept with: `!accepttrade`"
        )

    @commands.command(name="accepttrade", help="Accept the latest trade proposed to you.")
    async def accepttrade(self, ctx):
        p = TRADE_PROPOSALS.get(str(ctx.author.id))
        if not p:
            return await ctx.send("❌ You have no pending trade proposals.")

        if p.get("guild_id") and ctx.guild and p["guild_id"] != ctx.guild.id:
            return await ctx.send("❌ That trade was proposed in a different server/channel context.")

        proposer_id = int(p["from"])
        target_id = int(p["to"])
        give_item = str(p["give"])
        want_item = str(p["want"])

        # lock both inventories to avoid duplication
        first, second = sorted([proposer_id, target_id])
        async with MONEY_LOCKS[first], MONEY_LOCKS[second]:
            ensure_user_inventory(proposer_id)
            ensure_user_inventory(target_id)
            inv = load_inventory()

            proposer_inv = inv.get(str(proposer_id), {}) or {}
            target_inv = inv.get(str(target_id), {}) or {}

            # proposer must still have "give"
            if int(proposer_inv.get(give_item, 0)) <= 0:
                TRADE_PROPOSALS.pop(str(ctx.author.id), None)
                save_inventory(inv)
                return await ctx.send("❌ Trade failed: proposer no longer has the offered item.")

            # target must have "want" item to swap
            if int(target_inv.get(want_item, 0)) <= 0:
                return await ctx.send(f"❌ You can’t accept: you don’t have **{want_item}**.")

            # perform swap (1 item each)
            proposer_inv[give_item] = int(proposer_inv.get(give_item, 0)) - 1
            if proposer_inv[give_item] <= 0:
                proposer_inv.pop(give_item, None)

            target_inv[want_item] = int(target_inv.get(want_item, 0)) - 1
            if target_inv[want_item] <= 0:
                target_inv.pop(want_item, None)

            proposer_inv[want_item] = int(proposer_inv.get(want_item, 0)) + 1
            target_inv[give_item] = int(target_inv.get(give_item, 0)) + 1

            inv[str(proposer_id)] = proposer_inv
            inv[str(target_id)] = target_inv
            save_inventory(inv)

        TRADE_PROPOSALS.pop(str(ctx.author.id), None)

        proposer_user = await self.bot.fetch_user(proposer_id)
        await ctx.send(
            f"✅ Trade completed!\n"
            f"**{proposer_user.display_name}** gave **{give_item}** and received **{want_item}**."
        )

    # ---------- Stocks trading ----------
    @commands.command(name="portfolio", aliases=["pf"], help="Show your stock holdings.")
    async def portfolio(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        ensure_user_coins(member.id)
        coins = load_coins()
        u = coins[str(member.id)]
        pf = u.get("portfolio", {}) or {}

        stocks_data = load_json("stocks.json", {})
        lines = []
        total_value = 0

        for s in STOCKS:
            shares = int(pf.get(s, 0))
            if shares <= 0:
                continue
            price = int((stocks_data.get(s, {}) or {}).get("price", 0))
            value = shares * price
            total_value += value
            lines.append(f"• **{s}** — {shares} shares @ {_format_coins(price)} = **{_format_coins(value)}**")

        if not lines:
            return await ctx.send(embed=discord.Embed(description=f"📉 {member.display_name} has no stocks yet.", color=discord.Color.dark_grey()))

        embed = discord.Embed(
            title=f"📁 Portfolio — {member.display_name}",
            description="\n".join(lines)[:4000],
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Total stock value: {_format_coins(total_value)} coins")
        await ctx.send(embed=embed)

    @commands.command(name="buystock", help="Buy stock. Usage: !buystock <stock> <shares>")
    async def buystock(self, ctx, stock: str, shares: int):
        s = _match_stock(stock)
        if not s:
            return await ctx.send("❌ Unknown stock. Use `!stocks` to see names.")
        if shares <= 0:
            return await ctx.send("❌ Shares must be > 0.")

        uid = ctx.author.id
        async with MONEY_LOCKS[uid]:
            ensure_user_coins(uid)
            coins = load_coins()
            u = coins[str(uid)]

            stocks_data = load_json("stocks.json", {})
            price = int((stocks_data.get(s, {}) or {}).get("price", 0))
            if price <= 0:
                return await ctx.send("❌ Stock price unavailable right now.")

            cost = price * shares
            if int(u.get("wallet", 0)) < cost:
                return await ctx.send(f"💸 You need **{_format_coins(cost)}** coins in wallet.")

            u["wallet"] -= cost
            u.setdefault("portfolio", {})
            u["portfolio"][s] = int(u["portfolio"].get(s, 0)) + shares
            save_coins(coins)

        # optionally influence price updates (your old behaviour)
        try:
            from bot.cogs.stocks import STOCK_PURCHASE_COUNT
            STOCK_PURCHASE_COUNT[s] = int(STOCK_PURCHASE_COUNT.get(s, 0)) + shares
        except Exception:
            pass

        await ctx.send(embed=discord.Embed(
            description=f"✅ Bought **{shares}** shares of **{s}** for **{_format_coins(cost)}** coins.",
            color=discord.Color.green()
        ))

    @commands.command(name="sellstock", help="Sell stock. Usage: !sellstock <stock> <shares>")
    async def sellstock(self, ctx, stock: str, shares: int):
        s = _match_stock(stock)
        if not s:
            return await ctx.send("❌ Unknown stock. Use `!stocks` to see names.")
        if shares <= 0:
            return await ctx.send("❌ Shares must be > 0.")

        uid = ctx.author.id
        async with MONEY_LOCKS[uid]:
            ensure_user_coins(uid)
            coins = load_coins()
            u = coins[str(uid)]
            pf = u.get("portfolio", {}) or {}

            owned = int(pf.get(s, 0))
            if owned < shares:
                return await ctx.send(f"❌ You only own **{owned}** shares of **{s}**.")

            stocks_data = load_json("stocks.json", {})
            price = int((stocks_data.get(s, {}) or {}).get("price", 0))
            if price <= 0:
                return await ctx.send("❌ Stock price unavailable right now.")

            proceeds = price * shares
            pf[s] = owned - shares
            if pf[s] <= 0:
                pf.pop(s, None)
            u["portfolio"] = pf
            u["wallet"] = int(u.get("wallet", 0)) + proceeds
            coins[str(uid)] = u
            save_coins(coins)

        await ctx.send(embed=discord.Embed(
            description=f"✅ Sold **{shares}** shares of **{s}** for **{_format_coins(proceeds)}** coins.",
            color=discord.Color.green()
        ))

    # ---------- Shop restock loop ----------
    @tasks.loop(minutes=SHOP_RESTOCK_CHECK_MINUTES)
    async def shop_restock_loop(self):
        await self.bot.wait_until_ready()
        stock = load_shop_stock()
        changed = False
        restocked = []

        for item in SHOP_ITEMS:
            if random.random() < SHOP_RESTOCK_CHANCE:
                add = random.randint(1, SHOP_RESTOCK_MAX_ADD)
                stock[item] = int(stock.get(item, 0)) + add
                changed = True
                restocked.append((item, add))

        if not changed:
            return

        save_shop_stock(stock)

        # announce restock (optional)
        channel = self.bot.get_channel(MARKET_ANNOUNCE_CHANNEL_ID)
        if channel and restocked:
            lines = [f"• **{item}** +{add} (now {int(stock.get(item,0))})" for item, add in restocked]
            embed = discord.Embed(title="📦 Shop Restock", description="\n".join(lines)[:4000], color=discord.Color.blurple())
            try:
                await channel.send(embed=embed)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
