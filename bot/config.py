import os
from zoneinfo import ZoneInfo

# ===== Server restriction / IDs =====
RESTRICT_GUILD_NAME = "QMUL - Unofficial"

ANNOUNCEMENT_CHANNEL_ID = 1433248053665726547
WELCOME_CHANNEL_ID = 1433248053665726546
MARKET_ANNOUNCE_CHANNEL_ID = 1433412796531347586
SUGGESTION_CHANNEL_ID = 1433413006842396682
LEVEL_UP_CHANNEL_ID = 1433417692320239666

TOP_ROLE_NAME = "🌟 EXP Top"

# ===== Economy constants =====
INTEREST_RATE = 0.02
INTEREST_INTERVAL = 3600  # seconds
XP_PER_MESSAGE = 10

# ===== Bankrob constants =====
ALWAYS_BANKROB_USER_ID = 734468552903360594
BANKROB_STEAL_MIN_PCT = 0.12
BANKROB_STEAL_MAX_PCT = 0.28
BANKROB_MIN_STEAL = 100
BANKROB_MAX_STEAL_PCT_CAP = 0.40

# ===== Stocks =====
STOCKS = ["Oreobux", "QMkoin", "Seelsterling", "Fwizfinance", "BingBux"]
DIVIDEND_RATE = 0.01
DIVIDEND_INTERVAL = 86400  # seconds

# ===== Shop / Items =====
SHOP_ITEMS = ["Anime body pillow", "Oreo plush", "Rtx5090", "Crash token", "Imran's nose"]
ITEM_PRICES = {
    "Anime body pillow": 30000,
    "Oreo plush": 15000,
    "Rtx5090": 150000,
    "Crash token": 175000,
    "Imran's nose": 999999,
}
CRASH_TOKEN_NAME = "Crash token"

# ===== Minecraft =====
MC_NAME = "QMUL Survival"
MC_ADDRESS = "qmul-survival.modrinth.gg"
MC_JAVA_PORT = None  # SRV-based -> do not force port
MC_VERSION = "1.20.10"
MC_LOADER = "Fabric"
MC_MODPACK_NAME = "QMUL Survival Pack"
MC_WHITELISTED = False
MC_REGION = "UK / London"
MC_NOTES = [
    "Be respectful — no griefing.",
    "No x-ray / cheating clients.",
    "Ask an admin if you need help.",
]
MC_MODRINTH_URL = ""
MC_MAP_URL = ""
MC_RULES_URL = ""
MC_DISCORD_URL = "https://discord.gg/7uc8B4YN"
MC_SHOW_BEDROCK = False
MC_BEDROCK_PORT = 22165

# ===== Ramadan =====
BIC_TIMEZONE = "Europe/London"
BIC_POST_CHANNEL_ID = 1471992400351334626

# ===== Backups =====
PACKAGE_USER_ID = 734468552903360594
PACKAGE_FILES = [
    "data.json",
    "coins.json",
    "trivia_stats.json",
    "beg_stats.json",
    "prayer_notif_state.json",
    "ramadan_post_state.json",
]

# bot/config.py

EVENTS = {
    "Double XP": {"xp_mult": 2},
    "Crash Week": {"crash_odds": 0.3},
    "Boom Frenzy": {"boom_odds": 0.3},
    "Coin Rain": {"bonus_daily": 100},
}

