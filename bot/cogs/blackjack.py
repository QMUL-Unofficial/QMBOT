import random
import discord
from discord.ext import commands
from bot.cogs.economy import ensure_user_coins, load_coins, save_coins

SOLO_BLACKJACK_GAMES: dict[str, dict] = {}

_CARD_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
_CARD_SUITS = ["♠", "♥", "♦", "♣"]

def draw_card() -> str:
    return f"{random.choice(_CARD_RANKS)}{random.choice(_CARD_SUITS)}"

def _card_value(rank: str) -> int:
    if rank in ("J", "Q", "K"): return 10
    if rank == "A": return 11
    return int(rank)

def calculate_score(hand: list[str]) -> int:
    ranks = ["10" if c.startswith("10") else c[0] for c in hand]
    total = sum(_card_value(r) for r in ranks)
    aces = ranks.count("A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def _hand_as_text(cards: list[str]) -> str:
    return ", ".join(cards)

class Blackjack(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="blackjack", help="Play a solo game of blackjack. Usage: !blackjack <bet>")
    async def solo_blackjack(self, ctx: commands.Context, bet: int):
        user_id = str(ctx.author.id)
        if user_id in SOLO_BLACKJACK_GAMES:
            return await ctx.send("❌ You already have a solo Blackjack game in progress! Use `!hit` or `!stand`.")

        ensure_user_coins(user_id)
        coins = load_coins()
        user_data = coins[user_id]

        if bet <= 0:
            return await ctx.send("❌ Your bet must be more than zero.")
        if int(user_data["wallet"]) < bet:
            return await ctx.send("💸 You don’t have enough coins to bet that much.")

        user_data["wallet"] -= bet
        save_coins(coins)

        player_hand = [draw_card(), draw_card()]
        dealer_hand = [draw_card(), draw_card()]
        player_score = calculate_score(player_hand)

        SOLO_BLACKJACK_GAMES[user_id] = {"player_hand": player_hand, "dealer_hand": dealer_hand, "bet": bet}

        dealer_up = dealer_hand[0]
        embed = discord.Embed(
            title="🃏 Solo Blackjack",
            description=(
                f"**Your hand:** {_hand_as_text(player_hand)} (Total: **{player_score}**)\n"
                f"**Dealer shows:** {dealer_up}\n\n"
                "Type `!hit` to draw a card or `!stand` to hold."
            ),
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="hit", help="Draw a card in your solo Blackjack game.")
    async def solo_hit(self, ctx):
        user_id = str(ctx.author.id)
        if user_id not in SOLO_BLACKJACK_GAMES:
            return await ctx.send("❌ You don’t have a solo Blackjack game in progress. Use `!blackjack <bet>` to start.")

        game = SOLO_BLACKJACK_GAMES[user_id]
        game["player_hand"].append(draw_card())
        score = calculate_score(game["player_hand"])

        if score > 21:
            bet = game["bet"]
            final = _hand_as_text(game["player_hand"])
            del SOLO_BLACKJACK_GAMES[user_id]
            embed = discord.Embed(
                title="💥 Busted!",
                description=f"You drew: {final} (Total: **{score}**)\nYou lost **{bet}** coins.",
                color=discord.Color.red(),
            )
            return await ctx.send(embed=embed)

        embed = discord.Embed(
            title="🃏 You drew a card",
            description=f"Your hand: {_hand_as_text(game['player_hand'])} (Total: **{score}**)\nType `!hit` or `!stand`.",
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="stand", help="Stand and let the dealer play in solo Blackjack.")
    async def solo_stand(self, ctx):
        user_id = str(ctx.author.id)
        if user_id not in SOLO_BLACKJACK_GAMES:
            return await ctx.send("❌ You don’t have a solo Blackjack game in progress.")

        game = SOLO_BLACKJACK_GAMES.pop(user_id)
        player_hand = game["player_hand"]
        dealer_hand = game["dealer_hand"]
        bet = game["bet"]

        player_score = calculate_score(player_hand)
        dealer_score = calculate_score(dealer_hand)
        while dealer_score < 17:
            dealer_hand.append(draw_card())
            dealer_score = calculate_score(dealer_hand)

        ensure_user_coins(user_id)
        coins = load_coins()
        user_data = coins[user_id]

        if dealer_score > 21 or player_score > dealer_score:
            winnings = bet * 2
            user_data["wallet"] += winnings
            result_msg = f"🎉 You win! Dealer had {dealer_score}. You earned **{winnings}** coins!"
            color = discord.Color.green()
        elif dealer_score == player_score:
            user_data["wallet"] += bet
            result_msg = f"🤝 It’s a tie! Dealer had {dealer_score}. Your **{bet}** coins were returned."
            color = discord.Color.gold()
        else:
            result_msg = f"😢 You lost. Dealer had {dealer_score}. Better luck next time!"
            color = discord.Color.red()

        save_coins(coins)
        embed = discord.Embed(
            title="🏁 Final Result",
            description=(
                f"**Your hand:** {_hand_as_text(player_hand)} (Total: **{player_score}**)\n"
                f"**Dealer hand:** {_hand_as_text(dealer_hand)} (Total: **{dealer_score}**)\n\n"
                f"{result_msg}"
            ),
            color=color,
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Blackjack(bot))
