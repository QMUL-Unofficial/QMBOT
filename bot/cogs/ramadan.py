import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bot.config import BIC_TIMEZONE, BIC_POST_CHANNEL_ID
from bot.utils.storage import load_json, save_json, abs_path

BIC_RAMADAN_JSON = "bic_ramadan_2026.json"
RAMADAN_STATE_FILE = "ramadan_state.json"

def load_ramadan_config():
    data = load_json(BIC_RAMADAN_JSON, {})
    if not data or "days" not in data:
        raise RuntimeError(f"Missing or invalid {abs_path(BIC_RAMADAN_JSON)}")
    return data

def load_ramadan_state():
    return load_json(RAMADAN_STATE_FILE, {"sent": {}, "last_daily_post": ""})

def save_ramadan_state(state):
    save_json(RAMADAN_STATE_FILE, state)

def _parse_hhmm(date_str: str, hhmm: str, tz: ZoneInfo) -> datetime:
    hour, minute = hhmm.split(":")
    return datetime.fromisoformat(date_str).replace(
        hour=int(hour), minute=int(minute), second=0, microsecond=0, tzinfo=tz
    )

def format_day_text(cfg, entry, date_key: str) -> str:
    masjid = cfg.get("masjid_name", "Masjid")
    pretty = entry.get("pretty_date", date_key)
    rd = entry.get("ramadan_day", "")
    rd_txt = f" (Day {rd})" if rd else ""

    lines = [
        f"**{masjid} — Ramadan Timetable**",
        f"**{pretty}{rd_txt}**",
        "",
        f"🌙 **Suhur ends:** `{entry['suhur_ends']}`",
        f"🕌 **Fajr Jama'ah:** `{entry['fajr_jamaah']}`",
        f"🕛 **Zuhr Jama'ah:** `{entry['zuhr_jamaah']}`",
        f"🕓 **Asr Jama'ah:** `{entry['asr_jamaah']}`",
        "",
        f"🌅 **Iftar time:** `{entry['iftar_time']}`",
        f"🕌 **Maghrib Jama'ah:** `{entry['maghrib_jamaah']}`",
        f"🕌 **Isha Jama'ah:** `{entry['isha_jamaah']}`",
        f"🕌 **Taraweeh:** `{entry['taraweeh']}`",
    ]
    note = cfg.get("note")
    if note:
        lines += ["", f"ℹ️ {note}"]
    return "\n".join(lines)

async def _post_embed_to_channel(bot, channel_id: int, title: str, description: str, color: discord.Color):
    channel = bot.get_channel(channel_id)
    if not channel:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception:
            return
    embed = discord.Embed(title=title, description=description, color=color)
    await channel.send(embed=embed)

class Ramadan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ramadan_bic_scheduler.start()

    def cog_unload(self):
        self.ramadan_bic_scheduler.cancel()

    @tasks.loop(seconds=30)
    async def ramadan_bic_scheduler(self):
        await self.bot.wait_until_ready()

        cfg = load_ramadan_config()
        tz = ZoneInfo(cfg.get("timezone", BIC_TIMEZONE))
        channel_id = int(cfg.get("post_channel_id", BIC_POST_CHANNEL_ID))
        state = load_ramadan_state()

        now_local = datetime.now(tz)
        today_key = now_local.date().isoformat()
        entry = cfg["days"].get(today_key)

        if entry and state.get("last_daily_post") != today_key:
            if now_local.hour == 0 and now_local.minute >= 5:
                desc = format_day_text(cfg, entry, today_key)
                await _post_embed_to_channel(self.bot, channel_id, "🗓️ Today’s Ramadan Times", desc, discord.Color.gold())
                state["last_daily_post"] = today_key
                save_ramadan_state(state)

        if not entry:
            return

        reminders = cfg.get("reminders", {})
        reminder_specs = [
            ("suhur_ends", "⏳ Suhur Reminder", int(reminders.get("suhur_minutes_before", 30)),
             "Suhur ends at **{time}** — finish eating/drinking now."),
            ("iftar_time", "🌅 Iftar Reminder", int(reminders.get("iftar_minutes_before", 10)),
             "Iftar is at **{time}** — get ready."),
            ("taraweeh", "🕌 Taraweeh Reminder", int(reminders.get("taraweeh_minutes_before", 20)),
             "Taraweeh starts at **{time}** — time to head over."),
        ]

        for field, title, mins_before, template in reminder_specs:
            hhmm = entry.get(field)
            if not hhmm:
                continue

            event_dt = _parse_hhmm(today_key, hhmm, tz)
            remind_dt = event_dt - timedelta(minutes=mins_before)

            if remind_dt <= now_local < (remind_dt + timedelta(seconds=30)):
                sent_key = f"{today_key}:{field}:{mins_before}"
                if state["sent"].get(sent_key):
                    continue

                msg = template.format(time=hhmm)
                await _post_embed_to_channel(self.bot, channel_id, title, f"@everyone\n\n{msg}", discord.Color.orange())
                state["sent"][sent_key] = True
                save_ramadan_state(state)

    @commands.command(name="table", help="Show Ramadan times for today.")
    async def table(self, ctx: commands.Context):
        cfg = load_ramadan_config()
        tz = ZoneInfo(cfg.get("timezone", BIC_TIMEZONE))
        today_key = datetime.now(tz).date().isoformat()
        entry = cfg["days"].get(today_key)
        if not entry:
            return await ctx.send("❌ No timetable entry found for today.")
        desc = format_day_text(cfg, entry, today_key)
        embed = discord.Embed(title="🕌 Ramadan Times (Today)", description=desc, color=discord.Color.gold())
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Ramadan(bot))
