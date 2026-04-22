from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from utils import logger
from .exchange import ExchangeClient


# Standard (slow) flow timeframes — used by the legacy 4h analyzer.
TIMEFRAMES = ["15m", "1h", "4h", "1d"]
# Quick (scalp) flow timeframes — used by the meme/volatile engine.
QUICK_TIMEFRAMES = ["5m", "15m", "1h"]


class MarketDataService:
    def __init__(self, exchange: Optional[ExchangeClient] = None) -> None:
        self.exchange = exchange or ExchangeClient()

    def get_candles(self, symbol: str, timeframe: str = "1h", limit: int = 300) -> pd.DataFrame:
        raw = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    def get_multi_timeframe(
        self,
        symbol: str,
        timeframes: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        tfs = timeframes or TIMEFRAMES
        out: Dict[str, pd.DataFrame] = {}
        for tf in tfs:
            try:
                out[tf] = self.get_candles(symbol, tf, limit=300)
            except Exception as e:
                logger.warning(f"failed to fetch {symbol} {tf}: {e}")
        return out

    def get_ticker_snapshot(self, symbol: str) -> Dict:
        t = self.exchange.fetch_ticker(symbol)
        return {
            "symbol": symbol,
            "last": float(t.get("last") or 0.0),
            "bid": float(t.get("bid") or 0.0),
            "ask": float(t.get("ask") or 0.0),
            "high_24h": float(t.get("high") or 0.0),
            "low_24h": float(t.get("low") or 0.0),
            "change_24h_pct": float(t.get("percentage") or 0.0),
            "quote_volume_24h": float(t.get("quoteVolume") or 0.0),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_liquidity(self, symbol: str, depth: int = 20) -> Dict:
        # KuCoin only accepts depth in {20, 100}; 20 is sane for all exchanges.
        ob = self.exchange.fetch_order_book(symbol, limit=depth)
        bids = ob.get("bids") or []
        asks = ob.get("asks") or []
        bid_liquidity = sum(price * qty for price, qty in bids)
        ask_liquidity = sum(price * qty for price, qty in asks)
        spread = 0.0
        if bids and asks:
            spread = (asks[0][0] - bids[0][0]) / asks[0][0] * 100
        return {
            "bid_liquidity_usd": bid_liquidity,
            "ask_liquidity_usd": ask_liquidity,
            "total_liquidity_usd": bid_liquidity + ask_liquidity,
            "spread_pct": spread,
        }
