"""Technical indicators computed from OHLCV data.

Uses pandas-ta which is pure Python and does not require the C TA-Lib
system dependency.
"""
from __future__ import annotations

from typing import Dict, Any
import pandas as pd
import pandas_ta_classic as ta


def compute_indicators(df: pd.DataFrame) -> Dict[str, Any]:
    """Compute a comprehensive set of indicators on the latest closed candle."""
    if df is None or df.empty or len(df) < 60:
        return {}

    out: Dict[str, Any] = {}
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # Momentum
    rsi = ta.rsi(close, length=14)
    stoch = ta.stoch(high, low, close)
    macd = ta.macd(close)
    cci = ta.cci(high, low, close, length=20)

    # Trend
    ema9 = ta.ema(close, length=9)
    ema21 = ta.ema(close, length=21)
    ema50 = ta.ema(close, length=50)
    ema200 = ta.ema(close, length=200) if len(close) >= 200 else None
    sma50 = ta.sma(close, length=50)
    adx = ta.adx(high, low, close, length=14)

    # Volatility
    bb = ta.bbands(close, length=20, std=2)
    atr = ta.atr(high, low, close, length=14)

    # Volume
    obv = ta.obv(close, volume)
    vwap = ta.vwap(high, low, close, volume) if df.index.name == "timestamp" or "timestamp" in str(df.index.dtype) else None
    mfi = ta.mfi(high, low, close, volume, length=14)

    # Ichimoku
    try:
        ichi, _ = ta.ichimoku(high, low, close)
    except Exception:
        ichi = None

    last = -1

    def _last(s):
        try:
            v = s.iloc[last]
            return float(v) if v == v else None  # NaN check
        except Exception:
            return None

    out["price"] = float(close.iloc[last])
    out["rsi_14"] = _last(rsi) if rsi is not None else None
    out["stoch_k"] = _last(stoch["STOCHk_14_3_3"]) if stoch is not None else None
    out["stoch_d"] = _last(stoch["STOCHd_14_3_3"]) if stoch is not None else None
    out["macd"] = _last(macd["MACD_12_26_9"]) if macd is not None else None
    out["macd_signal"] = _last(macd["MACDs_12_26_9"]) if macd is not None else None
    out["macd_hist"] = _last(macd["MACDh_12_26_9"]) if macd is not None else None
    out["cci_20"] = _last(cci) if cci is not None else None

    out["ema_9"] = _last(ema9)
    out["ema_21"] = _last(ema21)
    out["ema_50"] = _last(ema50)
    out["ema_200"] = _last(ema200) if ema200 is not None else None
    out["sma_50"] = _last(sma50)

    if adx is not None and not adx.empty:
        out["adx_14"] = _last(adx["ADX_14"])
        out["di_plus"] = _last(adx["DMP_14"])
        out["di_minus"] = _last(adx["DMN_14"])

    if bb is not None and not bb.empty:
        out["bb_upper"] = _last(bb["BBU_20_2.0"])
        out["bb_middle"] = _last(bb["BBM_20_2.0"])
        out["bb_lower"] = _last(bb["BBL_20_2.0"])

    out["atr_14"] = _last(atr) if atr is not None else None
    out["obv"] = _last(obv) if obv is not None else None
    out["vwap"] = _last(vwap) if vwap is not None else None
    out["mfi_14"] = _last(mfi) if mfi is not None else None

    if ichi is not None and not ichi.empty:
        cols = list(ichi.columns)
        out["ichimoku_tenkan"] = _last(ichi[cols[0]]) if len(cols) > 0 else None
        out["ichimoku_kijun"] = _last(ichi[cols[1]]) if len(cols) > 1 else None
        out["ichimoku_senkou_a"] = _last(ichi[cols[2]]) if len(cols) > 2 else None
        out["ichimoku_senkou_b"] = _last(ichi[cols[3]]) if len(cols) > 3 else None

    # Volume average
    out["volume_avg_20"] = float(volume.tail(20).mean())
    out["volume_last"] = float(volume.iloc[last])
    out["volume_ratio"] = (out["volume_last"] / out["volume_avg_20"]) if out["volume_avg_20"] else 0.0

    return out


def detect_market_structure(df: pd.DataFrame, lookback: int = 30) -> str:
    """Return one of: bullish, bearish, ranging."""
    if df is None or len(df) < lookback + 2:
        return "ranging"
    recent = df.tail(lookback)
    highs = recent["high"].values
    lows = recent["low"].values
    # naive HH/HL or LH/LL detection
    higher_highs = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i - 1])
    higher_lows = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i - 1])
    bull_score = higher_highs + higher_lows
    bear_score = (len(highs) - 1 - higher_highs) + (len(lows) - 1 - higher_lows)
    diff = bull_score - bear_score
    if diff > lookback * 0.25:
        return "bullish"
    if diff < -lookback * 0.25:
        return "bearish"
    return "ranging"
