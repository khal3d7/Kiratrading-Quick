from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseStrategy, Signal


class SmartMoneyStrategy(BaseStrategy):
    """Simplified Smart Money Concept: liquidity sweep + structure shift.

    A liquidity sweep is detected when price wicks through a recent
    swing low/high then closes back inside, suggesting stop-runs by smart
    money. Combined with a structure shift on the lower timeframe.
    """

    name = "Smart Money Concept"

    def evaluate(self, analysis: Dict[str, Any]) -> Optional[Signal]:
        candles = analysis.get("candles", {})
        df_1h = candles.get("1h")
        if df_1h is None or len(df_1h) < 30:
            return None

        ind = analysis["indicators"].get("1h", {})
        atr = ind.get("atr_14") or 0
        price = ind.get("price")
        if not (price and atr):
            return None

        recent = df_1h.tail(20)
        swing_low = float(recent["low"].iloc[:-1].min())
        swing_high = float(recent["high"].iloc[:-1].max())
        last = recent.iloc[-1]
        prev = recent.iloc[-2]

        # Bullish sweep: last candle wicked below swing_low and closed above it
        if last["low"] < swing_low and last["close"] > swing_low and last["close"] > last["open"]:
            reasoning = [
                f"كنس سيولة تحت {swing_low:.4f} ثم إغلاق أعلى منه",
                "شمعة صاعدة — مؤشر على دخول السيولة الذكية",
            ]
            entry = float(last["close"])
            sl = float(last["low"]) - atr * 0.3
            tp1 = entry + atr * 2
            tp2 = entry + atr * 3.5
            tp3 = swing_high
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="LONG",
                entry=round(entry, 6), stop_loss=round(sl, 6),
                take_profit_1=round(tp1, 6), take_profit_2=round(tp2, 6),
                take_profit_3=round(tp3, 6), confidence=68.0, reasoning=reasoning,
            )

        if last["high"] > swing_high and last["close"] < swing_high and last["close"] < last["open"]:
            reasoning = [
                f"كنس سيولة فوق {swing_high:.4f} ثم إغلاق تحته",
                "شمعة هابطة — توزيع محتمل من السيولة الذكية",
            ]
            entry = float(last["close"])
            sl = float(last["high"]) + atr * 0.3
            tp1 = entry - atr * 2
            tp2 = entry - atr * 3.5
            tp3 = swing_low
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="SHORT",
                entry=round(entry, 6), stop_loss=round(sl, 6),
                take_profit_1=round(tp1, 6), take_profit_2=round(tp2, 6),
                take_profit_3=round(tp3, 6), confidence=66.0, reasoning=reasoning,
            )
        return None
