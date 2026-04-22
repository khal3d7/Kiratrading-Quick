"""Detect support/resistance levels using pivot clustering and Fibonacci."""
from __future__ import annotations

from typing import Dict, List
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema


def _cluster_levels(levels: List[float], tolerance_pct: float = 0.5) -> List[float]:
    if not levels:
        return []
    sorted_levels = sorted(levels)
    clusters: List[List[float]] = [[sorted_levels[0]]]
    for level in sorted_levels[1:]:
        last_cluster = clusters[-1]
        ref = sum(last_cluster) / len(last_cluster)
        if abs(level - ref) / ref * 100 <= tolerance_pct:
            last_cluster.append(level)
        else:
            clusters.append([level])
    return [round(sum(c) / len(c), 8) for c in clusters]


def find_support_resistance(df: pd.DataFrame, order: int = 5) -> Dict[str, List[float]]:
    """Detect S/R levels using local extrema and Fibonacci retracement.

    Returns up to 5 nearest support and 5 nearest resistance levels relative
    to the last price.
    """
    if df is None or df.empty or len(df) < order * 2 + 1:
        return {"support": [], "resistance": [], "fibonacci": {}}

    highs = df["high"].values
    lows = df["low"].values
    last_price = float(df["close"].iloc[-1])

    high_idx = argrelextrema(highs, np.greater, order=order)[0]
    low_idx = argrelextrema(lows, np.less, order=order)[0]

    resistance_raw = [float(highs[i]) for i in high_idx]
    support_raw = [float(lows[i]) for i in low_idx]

    resistances = _cluster_levels(resistance_raw)
    supports = _cluster_levels(support_raw)

    # filter relative to current price
    resistances = sorted([r for r in resistances if r > last_price])[:5]
    supports = sorted([s for s in supports if s < last_price], reverse=True)[:5]

    # Fibonacci over recent swing
    recent = df.tail(120)
    swing_high = float(recent["high"].max())
    swing_low = float(recent["low"].min())
    diff = swing_high - swing_low
    fib = {
        "0.0": round(swing_low, 8),
        "0.236": round(swing_low + diff * 0.236, 8),
        "0.382": round(swing_low + diff * 0.382, 8),
        "0.5": round(swing_low + diff * 0.5, 8),
        "0.618": round(swing_low + diff * 0.618, 8),
        "0.786": round(swing_low + diff * 0.786, 8),
        "1.0": round(swing_high, 8),
    }

    return {"support": supports, "resistance": resistances, "fibonacci": fib}


def pivot_points(df: pd.DataFrame) -> Dict[str, float]:
    """Classic daily pivot points from the previous candle."""
    if df is None or len(df) < 2:
        return {}
    prev = df.iloc[-2]
    high, low, close = float(prev["high"]), float(prev["low"]), float(prev["close"])
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)
    return {
        "pivot": round(pivot, 8),
        "r1": round(r1, 8), "r2": round(r2, 8), "r3": round(r3, 8),
        "s1": round(s1, 8), "s2": round(s2, 8), "s3": round(s3, 8),
    }
