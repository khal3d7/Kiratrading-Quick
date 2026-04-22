from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseStrategy, Signal


class BreakoutStrategy(BaseStrategy):
    name = "Breakout (S/R + Volume)"

    def evaluate(self, analysis: Dict[str, Any]) -> Optional[Signal]:
        ind = analysis["indicators"].get("4h", {})
        sr = analysis.get("support_resistance", {})
        if not ind or not sr:
            return None

        price = ind.get("price")
        atr = ind.get("atr_14") or 0
        vol_ratio = ind.get("volume_ratio") or 0
        rsi = ind.get("rsi_14") or 50
        if not (price and atr):
            return None

        resistances = sr.get("resistance", [])
        supports = sr.get("support", [])

        # Bullish breakout: price within 1% of nearest resistance, strong volume
        if resistances:
            nearest_res = resistances[0]
            distance_pct = (nearest_res - price) / price * 100
            if -0.5 <= distance_pct <= 1.0 and vol_ratio >= 1.5 and rsi < 75:
                reasoning = [
                    f"السعر قرب مقاومة {nearest_res:.4f}",
                    f"حجم التداول {vol_ratio:.2f}× المتوسط — اختراق محتمل",
                    f"RSI = {rsi:.1f} ضمن منطقة آمنة",
                ]
                entry = nearest_res * 1.002
                sl = entry - atr * 1.2
                tp1 = entry + atr * 2
                tp2 = entry + atr * 3.5
                tp3 = entry + atr * 5
                return Signal(
                    symbol=analysis["symbol"], strategy=self.name, direction="LONG",
                    entry=round(entry, 6), stop_loss=round(sl, 6),
                    take_profit_1=round(tp1, 6), take_profit_2=round(tp2, 6),
                    take_profit_3=round(tp3, 6), confidence=70.0, reasoning=reasoning,
                )

        if supports:
            nearest_sup = supports[0]
            distance_pct = (price - nearest_sup) / price * 100
            if -0.5 <= distance_pct <= 1.0 and vol_ratio >= 1.5 and rsi > 25:
                reasoning = [
                    f"السعر قرب دعم {nearest_sup:.4f}",
                    f"حجم التداول {vol_ratio:.2f}× المتوسط — كسر هابط محتمل",
                    f"RSI = {rsi:.1f}",
                ]
                entry = nearest_sup * 0.998
                sl = entry + atr * 1.2
                tp1 = entry - atr * 2
                tp2 = entry - atr * 3.5
                tp3 = entry - atr * 5
                return Signal(
                    symbol=analysis["symbol"], strategy=self.name, direction="SHORT",
                    entry=round(entry, 6), stop_loss=round(sl, 6),
                    take_profit_1=round(tp1, 6), take_profit_2=round(tp2, 6),
                    take_profit_3=round(tp3, 6), confidence=68.0, reasoning=reasoning,
                )
        return None
