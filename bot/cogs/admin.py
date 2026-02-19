import io
import os
import zipfile
import discord
from discord.ext import commands, tasks
from datetime import datetime, timezone

from bot.config import ANNOUNCEMENT_CHANNEL_ID, INTEREST_INTERVAL, INTEREST_RATE, PACKAGE_USER_ID, PACKAGE_FILES
from bot.utils.storage import load_json, save_json, abs_path, exists_file

COIN_DATA_FILE = "coins.json"

def load_coins(): return load_json(COIN_DATA_FILE, {})
def save_coins(d): save_json(COIN_DATA_FILE, d)

def existing_files(files: list[str]) -> list[str]:
    out = []
    for f in files:
        if exists_file(f):
            out.append(abs_path(f))
    return out

async def build_data_zip_bytes() -> tuple[io.BytesIO, list[str]]:
    included = existing_files(PACKAGE_FILES)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        for path in included:
            arcname = f"bot_backup/{os.path.basename(path)}"
            z.write(path, arcname=arcname)
    buf.seek(0)
    return buf, included

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.apply_bank_interest.start()
        self.send_backup_zip_every_5h.start()

    def cog_unload(self):
        self.apply_bank_interest.cancel()
        self.send_backup_zip_every_5h.cancel()

    @commands.command(name="announcement", help="Post a yellow-embed announcement with @everyone")
    async def announcement(self, ctx, *, message: str):
        channel = self.bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
        if not channel:
            return await ctx.send("❌ Announcement channel not found.")
        embed = discord.Embed(description=message, color=discord.Color.yellow())
        await channel.send(content="@everyone", embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True))
        await ctx.send(f"✅ Announcement sent in {channel.mention}")

    @tasks.loop(seconds=INTEREST_INTERVAL)
    async def apply_bank_interest(self):
        await self.bot.wait_until_ready()
        coins = load_coins()
        changed = False
        for _, balances in coins.items():
            bank_balance = int(balances.get("bank", 0))
            if bank_balance > 0:
                interest = int(bank_balance * INTEREST_RATE)
                if interest > 0:
                    balances["bank"] = bank_balance + interest
                    changed = True
        if changed:
            save_coins(coins)
            print("[Interest] Applied interest to bank balances.")

    @tasks.loop(hours=5)
    async def send_backup_zip_every_5h(self):
        await self.bot.wait_until_ready()
        await self.dm_package_to_user(PACKAGE_USER_ID, reason="Every 5 hours")

    @send_backup_zip_every_5h.before_loop
    async def _before_send_backup_zip_every_5h(self):
        await self.bot.wait_until_ready()
        await self.dm_package_to_user(PACKAGE_USER_ID, reason="Bot started")

    async def dm_package_to_user(self, user_id: int, *, reason: str = "Scheduled backup"):
        try:
            user = await self.bot.fetch_user(int(user_id))
        except Exception as e:
            print(f"[Package] Failed to fetch user {user_id}: {e}")
            return False

        try:
            zip_buf, included = await build_data_zip_bytes()
            if not included:
                await user.send(f"⚠️ Backup attempt ({reason}) — no files found to package.")
                return True

            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S_UTC")
            file = discord.File(zip_buf, filename=f"qmul_bot_backup_{ts}.zip")

            msg = f"📦 **Bot Backup** ({reason})\nIncluded: {', '.join(os.path.basename(x) for x in included)}"
            await user.send(content=msg, file=file)
            print(f"[Package] Sent backup zip to {user_id} ({len(included)} files).")
            return True

        except discord.Forbidden:
            print(f"[Package] DM failed: user {user_id} has DMs closed or bot blocked.")
            return False
        except Exception as e:
            print(f"[Package] Error building/sending zip: {e}")
            return False

    @commands.command(name="package", help="DM the latest data backup zip to the package user.")
    async def package_cmd(self, ctx):
        if ctx.author.id != PACKAGE_USER_ID and not ctx.author.guild_permissions.administrator:
            return await ctx.send("❌ You don’t have permission to use this command.")
        ok = await self.dm_package_to_user(PACKAGE_USER_ID, reason=f"Manual !package by {ctx.author} ({ctx.author.id})")
        await ctx.send("✅ Backup zip sent via DM." if ok else "⚠️ Tried to DM the backup, but it failed.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
