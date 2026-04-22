from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional

from utils import logger
from data import MarketDataService
from .indicators import compute_indicators, detect_market_structure
from .support_resistance import find_support_resistance, pivot_points


class Analyzer:
    """Orchestrates a full analysis run for one symbol."""

    def __init__(self, market: Optional[MarketDataService] = None) -> None:
        self.market = market or MarketDataService()

    def analyze(
        self,
        symbol: str,
        primary_tf: str = "4h",
        timeframes: Optional[list] = None,
    ) -> Dict[str, Any]:
        logger.info(f"analyzing {symbol} on {primary_tf}")
        candles = self.market.get_multi_timeframe(symbol, timeframes=timeframes)
        if primary_tf not in candles:
            logger.warning(f"no data for {symbol} on {primary_tf}")
            return {}

        df_primary = candles[primary_tf]
        ticker = self.market.get_ticker_snapshot(symbol)
        liquidity = {}
        try:
            liquidity = self.market.get_liquidity(symbol)
        except Exception as e:
            logger.warning(f"liquidity fetch failed for {symbol}: {e}")

        indicators_per_tf: Dict[str, Dict[str, Any]] = {}
        for tf, df in candles.items():
            indicators_per_tf[tf] = compute_indicators(df)

        sr = find_support_resistance(df_primary)
        pivots = pivot_points(df_primary)
        structure = detect_market_structure(df_primary)

        return {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "primary_timeframe": primary_tf,
            "ticker": ticker,
            "liquidity": liquidity,
            "indicators": indicators_per_tf,
            "support_resistance": sr,
            "pivots": pivots,
            "market_structure": structure,
            "candles": {tf: df for tf, df in candles.items()},  # in-memory only
        }
