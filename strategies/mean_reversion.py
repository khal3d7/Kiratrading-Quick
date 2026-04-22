from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseStrategy, Signal


class MeanReversionStrategy(BaseStrategy):
    name = "Mean Reversion (BB + RSI)"

    def evaluate(self, analysis: Dict[str, Any]) -> Optional[Signal]:
        ind = analysis["indicators"].get("1h", {})
        ind_d = analysis["indicators"].get("1d", {})
        if not ind or not ind_d:
            return None

        price = ind.get("price")
        bb_lower = ind.get("bb_lower")
        bb_upper = ind.get("bb_upper")
        bb_middle = ind.get("bb_middle")
        rsi = ind.get("rsi_14") or 50
        atr = ind.get("atr_14") or 0
        ema200_d = ind_d.get("ema_200")
        if not (price and bb_lower and bb_upper and bb_middle and atr):
            return None

        # Long: oversold bounce in a longer-term uptrend
        if price <= bb_lower * 1.005 and rsi < 30 and ema200_d and price > ema200_d:
            reasoning = [
                f"السعر {price:.4f} عند بولينجر السفلي {bb_lower:.4f}",
                f"RSI = {rsi:.1f} في منطقة تشبع بيعي",
                "السعر فوق EMA200 اليومي — الاتجاه العام صاعد",
            ]
            entry = price
            sl = entry - atr * 1.0
            tp1 = bb_middle
            tp2 = bb_upper
            tp3 = bb_upper + atr
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="LONG",
                entry=round(entry, 6), stop_loss=round(sl, 6),
                take_profit_1=round(tp1, 6), take_profit_2=round(tp2, 6),
                take_profit_3=round(tp3, 6), confidence=65.0, reasoning=reasoning,
            )

        if price >= bb_upper * 0.995 and rsi > 70 and ema200_d and price < ema200_d:
            reasoning = [
                f"السعر {price:.4f} عند بولينجر العلوي {bb_upper:.4f}",
                f"RSI = {rsi:.1f} في منطقة تشبع شرائي",
                "السعر تحت EMA200 اليومي — الاتجاه العام هابط",
            ]
            entry = price
            sl = entry + atr * 1.0
            tp1 = bb_middle
            tp2 = bb_lower
            tp3 = bb_lower - atr
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="SHORT",
                entry=round(entry, 6), stop_loss=round(sl, 6),
                take_profit_1=round(tp1, 6), take_profit_2=round(tp2, 6),
                take_profit_3=round(tp3, 6), confidence=63.0, reasoning=reasoning,
            )
        return None
