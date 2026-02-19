import random
import numpy as np
import discord
from discord.ext import commands

wall = "⬜"
innerWall = "⬛"
energy = "🍎"
snakeHead = "😍"
snakeBody = "🟨"
snakeLoose = "😵"

SNAKE_GAMES = {}  # channel_id -> state
SNAKE_CONTROLS = {"⬆️":"up","⬇️":"down","⬅️":"left","➡️":"right","🔄":"reset"}

def _snake_new_matrix():
    return np.array([
        [0]*12,
        [0]+[1]*10+[0],
        [0]+[1]*10+[0],
        [0]+[1]*9 +[2]+[0],
        [0]+[1]*10+[0],
        [0]+[1]*10+[0],
        [0]+[1]*10+[0],
        [0]+[1]*10+[0],
        [0]+[1]*10+[0],
        [0]+[1]*10+[0],
        [0]+[1]*10+[0],
        [0]*12,
    ])

def _snake_generate_energy(state):
    m = state["matrix"]
    for _ in range(200):
        i = random.randint(1,10)
        j = random.randint(1,10)
        if m[i][j] == 1:
            m[i][j] = 4
            return

def _snake_grid_to_text(m):
    out = []
    for row in m:
        line = []
        for v in row:
            if v == 0: line.append(wall)
            elif v == 1: line.append(innerWall)
            elif v == 2: line.append(snakeHead)
            elif v == 3: line.append(snakeBody)
            elif v == 4: line.append(energy)
            else: line.append(snakeLoose)
        out.append("".join(line))
    return "\n".join(out)

def _snake_is_boundary(i, j):
    return i == 0 or j == 0 or i == 11 or j == 11

def _snake_handle_energy(state, i, j):
    m = state["matrix"]
    if m[i][j] == 4:
        state["points"] += 1
        _snake_generate_energy(state)

def _snake_update_head(state, ni, nj):
    m = state["matrix"]
    head = np.argwhere(m == 2)
    if head.size == 0:
        return
    hi, hj = head[0]
    m[ni][nj] = 2
    m[hi][hj] = 1

def _snake_move(state, direction):
    if state["is_out"]:
        return
    m = state["matrix"]
    hi, hj = np.argwhere(m == 2)[0]
    di, dj = 0, 0
    if direction == "up": di = -1
    elif direction == "down": di = 1
    elif direction == "left": dj = -1
    elif direction == "right": dj = 1

    ni, nj = hi + di, hj + dj
    if _snake_is_boundary(ni, nj):
        m[hi][hj] = 5
        state["is_out"] = True
        return

    _snake_handle_energy(state, ni, nj)
    _snake_update_head(state, ni, nj)

async def _snake_render(channel: discord.abc.Messageable, state, *, title="Pick Apple Game"):
    desc = _snake_grid_to_text(state["matrix"])
    embed = discord.Embed(title=title, description=desc, color=discord.Color.green())
    embed.add_field(name="Your Score", value=state["points"], inline=True)

    if state.get("msg_id"):
        try:
            msg = await channel.fetch_message(state["msg_id"])
            await msg.edit(embed=embed)
            return msg
        except Exception:
            state["msg_id"] = None

    msg = await channel.send(embed=embed)
    state["msg_id"] = msg.id
    for emoji in ("⬆️","⬇️","⬅️","➡️","🔄"):
        try: await msg.add_reaction(emoji)
        except Exception: pass
    return msg

def _snake_reset_state():
    state = {"matrix": _snake_new_matrix(), "points": 0, "is_out": False, "msg_id": None}
    _snake_generate_energy(state)
    return state

class Snake(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="snake", help="Play the emoji snake! Usage: !snake start | !snake w/a/s/d | !snake reset")
    async def snake_cmd(self, ctx, action: str = "start"):
        ch_id = ctx.channel.id
        action = action.lower()

        if action in ("start", "reset"):
            SNAKE_GAMES[ch_id] = _snake_reset_state()
            await _snake_render(ctx.channel, SNAKE_GAMES[ch_id], title=f"Pick Apple Game • {ctx.author.display_name}")
            await ctx.send("Use reactions ⬆️ ⬇️ ⬅️ ➡️ to move, or `!snake w/a/s/d`. `!snake reset` to restart.")
            return

        if ch_id not in SNAKE_GAMES:
            SNAKE_GAMES[ch_id] = _snake_reset_state()

        move_map = {"w":"up","a":"left","s":"down","d":"right","up":"up","down":"down","left":"left","right":"right"}
        if action not in move_map:
            return await ctx.send("❌ Invalid action. Use `start`, `reset`, or one of `w/a/s/d`.")

        state = SNAKE_GAMES[ch_id]
        if state["is_out"]:
            return await ctx.send(embed=discord.Embed(title="Game Over", description=f"Final score: **{state['points']}**", color=discord.Color.red()))

        _snake_move(state, move_map[action])
        await _snake_render(ctx.channel, state)

        if state["is_out"]:
            await ctx.send(embed=discord.Embed(title="Game Over", description=f"Scored: **{state['points']}**", color=discord.Color.red()))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == (self.bot.user.id if self.bot.user else None):
            return
        state = SNAKE_GAMES.get(payload.channel_id)
        if not state or not state.get("msg_id") or payload.message_id != state["msg_id"]:
            return

        action = SNAKE_CONTROLS.get(str(payload.emoji))
        if not action:
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        if action == "reset":
            SNAKE_GAMES[payload.channel_id] = _snake_reset_state()
            await _snake_render(channel, SNAKE_GAMES[payload.channel_id])
            return

        if state["is_out"]:
            return

        _snake_move(state, action)
        await _snake_render(channel, state)

async def setup(bot: commands.Bot):
    await bot.add_cog(Snake(bot))
