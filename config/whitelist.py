"""Approved coins for analysis and trading.

Two universes:
- WHITELIST: large-cap coins traded on the *standard* (4h) flow.
- MEME_WHITELIST: high-volatility / memecoins traded on the *quick* (5m)
  scalp flow with tight stops and 30-minute expiry.
"""
from __future__ import annotations

WHITELIST: list[str] = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "BNB/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "LINK/USDT",
    "DOT/USDT",
    "POL/USDT",
    "ATOM/USDT",
    "NEAR/USDT",
    "LTC/USDT",
    "TRX/USDT",
]

# Volatile / meme coins traded only via the quick-scalp engine.
MEME_WHITELIST: list[str] = [
    "DOGE/USDT",
    "SHIB/USDT",
    "PEPE/USDT",
    "FLOKI/USDT",
    "BONK/USDT",
    "WIF/USDT",
    "MEME/USDT",
    "TRUMP/USDT",
]

# Legacy blacklist kept for the standard flow.
BLACKLIST: set[str] = set()

# Liquidity filters (standard flow only)
MIN_MARKET_CAP_USD: float = 1_000_000_000
MIN_DAILY_VOLUME_USD: float = 50_000_000
MAX_HOURLY_MOVE_PCT: float = 30.0
