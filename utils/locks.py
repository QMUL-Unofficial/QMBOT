import asyncio
from collections import defaultdict

MONEY_LOCKS = defaultdict(asyncio.Lock)
