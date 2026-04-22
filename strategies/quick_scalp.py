"""Quick-scalp strategies tuned for volatile/meme coins on 5-minute charts.

Key differences from the standard 4h strategies:
- Tight ATR-based stops (~0.7×ATR)
- Short profit targets (1× / 1.5× / 2× ATR) so targets are reachable in
  the 15-30 minute holding window.
- Looser R/R minimum (~1.2) — speed matters more than payout.
- Looks at 5m primarily and confirms with 15m trend.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseStrategy, Signal


def _ind(analysis: Dict[str, Any], tf: str) -> Dict[str, Any]:
    return analysis.get("indicators", {}).get(tf, {}) or {}


class QuickMomentumStrategy(BaseStrategy):
    """Catch fast momentum thrusts on volatile coins.

    Enters when the 5m candle shows a strong directional impulse (RSI
    leaving neutral with rising MACD histogram) AND volume is above
    average AND the 15m higher-timeframe trend agrees.
    """
    name = "Quick Momentum (5m)"

    def evaluate(self, analysis: Dict[str, Any]) -> Optional[Signal]:
        m5 = _ind(analysis, "5m")
        m15 = _ind(analysis, "15m")
        if not m5:
            return None

        price = m5.get("price")
        atr = m5.get("atr_14") or 0
        rsi = m5.get("rsi_14") or 50
        macd = m5.get("macd") or 0
        macd_sig = m5.get("macd_signal") or 0
        vol_ratio = m5.get("volume_ratio") or 0
        ema50_5 = m5.get("ema_50") or price
        ema50_15 = m15.get("ema_50") if m15 else None
        price_15 = m15.get("price") if m15 else None

        if not (price and atr and atr > 0):
            return None
        if vol_ratio < 1.3:
            return None  # need extra volume to confirm impulse

        # Bullish impulse
        bull = (
            55 <= rsi <= 75
            and macd > macd_sig
            and price > ema50_5
            and (ema50_15 is None or price_15 is None or price_15 >= ema50_15)
        )
        # Bearish impulse
        bear = (
            25 <= rsi <= 45
            and macd < macd_sig
            and price < ema50_5
            and (ema50_15 is None or price_15 is None or price_15 <= ema50_15)
        )

        if bull:
            entry = price
            sl = entry - atr * 0.7
            tp1 = entry + atr * 1.0
            tp2 = entry + atr * 1.5
            tp3 = entry + atr * 2.0
            reasoning = [
                "زخم صاعد لحظي على إطار 5د",
                f"RSI = {rsi:.1f} في منطقة الزخم",
                f"MACD > الإشارة، السعر فوق EMA50",
                f"حجم {vol_ratio:.2f}× المتوسط — اندفاع مؤكد",
            ]
            if ema50_15 and price_15 and price_15 >= ema50_15:
                reasoning.append("الإطار الأعلى (15د) يدعم الاتجاه الصاعد")
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="LONG",
                entry=round(entry, 8), stop_loss=round(sl, 8),
                take_profit_1=round(tp1, 8), take_profit_2=round(tp2, 8),
                take_profit_3=round(tp3, 8), confidence=72.0, reasoning=reasoning,
            )

        if bear:
            entry = price
            sl = entry + atr * 0.7
            tp1 = entry - atr * 1.0
            tp2 = entry - atr * 1.5
            tp3 = entry - atr * 2.0
            reasoning = [
                "زخم هابط لحظي على إطار 5د",
                f"RSI = {rsi:.1f} في منطقة ضعف",
                f"MACD < الإشارة، السعر تحت EMA50",
                f"حجم {vol_ratio:.2f}× المتوسط — ضغط بائعين",
            ]
            if ema50_15 and price_15 and price_15 <= ema50_15:
                reasoning.append("الإطار الأعلى (15د) يدعم الاتجاه الهابط")
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="SHORT",
                entry=round(entry, 8), stop_loss=round(sl, 8),
                take_profit_1=round(tp1, 8), take_profit_2=round(tp2, 8),
                take_profit_3=round(tp3, 8), confidence=70.0, reasoning=reasoning,
            )
        return None


class QuickReversalStrategy(BaseStrategy):
    """Counter-trend snap-back on extreme RSI on 5m."""
    name = "Quick Reversal (5m)"

    def evaluate(self, analysis: Dict[str, Any]) -> Optional[Signal]:
        m5 = _ind(analysis, "5m")
        if not m5:
            return None
        price = m5.get("price")
        atr = m5.get("atr_14") or 0
        rsi = m5.get("rsi_14") or 50
        bb_u = m5.get("bb_upper")
        bb_l = m5.get("bb_lower")
        vol_ratio = m5.get("volume_ratio") or 0
        if not (price and atr and atr > 0):
            return None

        # Oversold bounce
        if rsi <= 22 and bb_l and price <= bb_l * 1.005 and vol_ratio >= 1.2:
            entry = price
            sl = entry - atr * 0.6
            tp1 = entry + atr * 0.9
            tp2 = entry + atr * 1.4
            tp3 = entry + atr * 1.9
            reasoning = [
                f"RSI = {rsi:.1f} (تشبّع بيع شديد)",
                "السعر لامس الباند السفلي لبولينجر",
                f"حجم {vol_ratio:.2f}× يعزّز احتمال الارتداد",
            ]
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="LONG",
                entry=round(entry, 8), stop_loss=round(sl, 8),
                take_profit_1=round(tp1, 8), take_profit_2=round(tp2, 8),
                take_profit_3=round(tp3, 8), confidence=66.0, reasoning=reasoning,
            )
        # Overbought reject
        if rsi >= 78 and bb_u and price >= bb_u * 0.995 and vol_ratio >= 1.2:
            entry = price
            sl = entry + atr * 0.6
            tp1 = entry - atr * 0.9
            tp2 = entry - atr * 1.4
            tp3 = entry - atr * 1.9
            reasoning = [
                f"RSI = {rsi:.1f} (تشبّع شراء شديد)",
                "السعر لامس الباند العلوي لبولينجر",
                f"حجم {vol_ratio:.2f}× يعزّز احتمال الانعكاس",
            ]
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="SHORT",
                entry=round(entry, 8), stop_loss=round(sl, 8),
                take_profit_1=round(tp1, 8), take_profit_2=round(tp2, 8),
                take_profit_3=round(tp3, 8), confidence=64.0, reasoning=reasoning,
            )
        return None
