import random
import discord
from discord.ext import commands, tasks

from bot.config import STOCKS, MARKET_ANNOUNCE_CHANNEL_ID, DIVIDEND_RATE, DIVIDEND_INTERVAL
from bot.utils.storage import load_json, save_json

STOCK_FILE = "stocks.json"
COIN_DATA_FILE = "coins.json"

STOCK_PURCHASE_COUNT = {s: 0 for s in STOCKS}

def load_coins(): return load_json(COIN_DATA_FILE, {})
def save_coins(d): save_json(COIN_DATA_FILE, d)

def save_stocks(d): save_json(STOCK_FILE, d)

def load_stocks():
    data = load_json(STOCK_FILE, None)
    template = {
        "Oreobux": {"price": 100, "history": [100]},
        "QMkoin": {"price": 150, "history": [150]},
        "Seelsterling": {"price": 200, "history": [200]},
        "Fwizfinance": {"price": 250, "history": [250]},
        "BingBux": {"price": 120, "history": [120]},
    }
    if data is None:
        save_stocks(template)
        return template

    changed = False
    fixed = {}
    for key in STOCKS:
        entry = data.get(key)
        if not entry:
            for k in data.keys():
                if k.lower() == key.lower():
                    entry = data[k]
                    changed = True
                    break
        if not entry or "price" not in entry or "history" not in entry:
            fixed[key] = template[key]
            changed = True
        else:
            fixed[key] = entry

    if changed:
        save_stocks(fixed)
    return fixed

class Stocks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_stock_prices.start()
        self.pay_dividends.start()

    def cog_unload(self):
        self.update_stock_prices.cancel()
        self.pay_dividends.cancel()

    @commands.command(name="stocks", help="View current stock prices.")
    async def stocks_cmd(self, ctx):
        stock_data = load_stocks()
        embed = discord.Embed(title="📈 Current Stock Prices", color=discord.Color.green())
        for name in STOCKS:
            price = int(stock_data[name]["price"])
            embed.add_field(name=name, value=f"💰 {price} coins", inline=True)
        await ctx.send(embed=embed)

    @tasks.loop(minutes=5)
    async def update_stock_prices(self):
        await self.bot.wait_until_ready()
        global STOCK_PURCHASE_COUNT

        stocks = load_stocks()
        total_purchases = sum(STOCK_PURCHASE_COUNT.values())
        growth_bias = random.uniform(0.01, 0.02)

        crash_triggered = random.randint(1, 15) == 1
        boom_triggered  = random.randint(1, 15) == 1
        mega_crash_triggered = random.randint(1, 100) == 1
        mega_boom_triggered  = random.randint(1, 100) == 1

        crash_multiplier       = random.uniform(0.4, 0.8)
        boom_multiplier        = random.uniform(2.3, 2.8)
        mega_crash_multiplier  = random.uniform(0.1, 0.3)
        mega_boom_multiplier   = random.uniform(6.0, 7.0)

        crashed, boomed, mega_crashed, mega_boomed = [], [], [], []

        for s in STOCKS:
            current_price = int(stocks[s]["price"])
            purchase_count = STOCK_PURCHASE_COUNT.get(s, 0)

            if mega_crash_triggered and current_price > 10000:
                new_price = max(1, int(current_price * mega_crash_multiplier))
                mega_crashed.append((s, current_price, new_price))
            elif crash_triggered and current_price > 5000:
                new_price = max(1, int(current_price * crash_multiplier))
                crashed.append((s, current_price, new_price))
            elif mega_boom_triggered and current_price < 2000:
                new_price = int(current_price * mega_boom_multiplier)
                mega_boomed.append((s, current_price, new_price))
            elif boom_triggered and current_price < 3000:
                new_price = int(current_price * boom_multiplier)
                boomed.append((s, current_price, new_price))
            else:
                if total_purchases > 0:
                    purchase_ratio = purchase_count / total_purchases
                    change = 0.5 * (purchase_ratio - 0.25) + growth_bias
                else:
                    change = random.uniform(-0.05, 0.05) + growth_bias
                new_price = max(1, int(current_price * (1 + change)))

            stocks[s]["price"] = new_price
            stocks[s]["history"].append(new_price)
            if len(stocks[s]["history"]) > 24:
                stocks[s]["history"] = stocks[s]["history"][-24:]

        save_stocks(stocks)
        STOCK_PURCHASE_COUNT = {s: 0 for s in STOCKS}

        channel = self.bot.get_channel(MARKET_ANNOUNCE_CHANNEL_ID)
        if not channel:
            return

        if mega_crashed:
            desc = "\n".join(f"💥 **{s}** plummeted from **{old}** → **{new}** coins" for s, old, new in mega_crashed)
            await channel.send(embed=discord.Embed(title="💀 MEGA CRASH!", description=f"A catastrophic collapse hit the market!\n\n{desc}", color=discord.Color.dark_red()))
        if crashed:
            desc = "\n".join(f"🔻 **{s}** crashed from **{old}** → **{new}** coins" for s, old, new in crashed)
            await channel.send(embed=discord.Embed(title="📉 Market Crash!", description=f"Some overvalued stocks took a hit:\n\n{desc}", color=discord.Color.red()))
        if mega_boomed:
            desc = "\n".join(f"🚀 **{s}** exploded from **{old}** → **{new}** coins" for s, old, new in mega_boomed)
            await channel.send(embed=discord.Embed(title="🚨 MEGA BOOM!", description=f"Insane surges swept the market!\n\n{desc}", color=discord.Color.gold()))
        if boomed:
            desc = "\n".join(f"📈 **{s}** rose from **{old}** → **{new}** coins" for s, old, new in boomed)
            await channel.send(embed=discord.Embed(title="📈 Market Boom!", description=f"Undervalued stocks surged upward:\n\n{desc}", color=discord.Color.green()))

    @tasks.loop(seconds=DIVIDEND_INTERVAL)
    async def pay_dividends(self):
        await self.bot.wait_until_ready()
        coins = load_coins()
        stocks = load_stocks()
        any_payout = False

        for user_id, data in coins.items():
            pf = (data.get("portfolio") or {})
            total_value = 0
            for s in STOCKS:
                total_value += int(pf.get(s, 0)) * int(stocks[s]["price"])
            payout = int(total_value * DIVIDEND_RATE)
            if payout > 0:
                data["wallet"] = int(data.get("wallet", 0)) + payout
                any_payout = True

        if any_payout:
            save_coins(coins)
            ch = self.bot.get_channel(MARKET_ANNOUNCE_CHANNEL_ID)
            if ch:
                await ch.send("💸 Dividends have been paid out to all shareholders!")

async def setup(bot: commands.Bot):
    await bot.add_cog(Stocks(bot))
