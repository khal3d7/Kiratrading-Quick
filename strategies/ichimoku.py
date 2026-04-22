from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseStrategy, Signal


class IchimokuStrategy(BaseStrategy):
    name = "Ichimoku Cloud"

    def evaluate(self, analysis: Dict[str, Any]) -> Optional[Signal]:
        ind = analysis["indicators"].get("4h", {})
        if not ind:
            return None

        price = ind.get("price")
        tenkan = ind.get("ichimoku_tenkan")
        kijun = ind.get("ichimoku_kijun")
        senkou_a = ind.get("ichimoku_senkou_a")
        senkou_b = ind.get("ichimoku_senkou_b")
        atr = ind.get("atr_14") or 0
        if not (price and tenkan and kijun and senkou_a and senkou_b and atr):
            return None

        cloud_top = max(senkou_a, senkou_b)
        cloud_bot = min(senkou_a, senkou_b)

        # Bullish: price above cloud, tenkan > kijun, cloud is green
        if price > cloud_top and tenkan > kijun and senkou_a > senkou_b:
            reasoning = [
                f"السعر {price:.4f} فوق سحابة إيشيموكو ({cloud_top:.4f})",
                "Tenkan فوق Kijun — زخم صاعد",
                "السحابة خضراء — تأكيد للاتجاه",
            ]
            entry = price
            sl = max(kijun, cloud_top) - atr * 0.5
            tp1 = entry + atr * 2
            tp2 = entry + atr * 4
            tp3 = entry + atr * 6
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="LONG",
                entry=round(entry, 6), stop_loss=round(sl, 6),
                take_profit_1=round(tp1, 6), take_profit_2=round(tp2, 6),
                take_profit_3=round(tp3, 6), confidence=72.0, reasoning=reasoning,
            )

        if price < cloud_bot and tenkan < kijun and senkou_a < senkou_b:
            reasoning = [
                f"السعر {price:.4f} تحت سحابة إيشيموكو ({cloud_bot:.4f})",
                "Tenkan تحت Kijun — زخم هابط",
                "السحابة حمراء — تأكيد للاتجاه",
            ]
            entry = price
            sl = min(kijun, cloud_bot) + atr * 0.5
            tp1 = entry - atr * 2
            tp2 = entry - atr * 4
            tp3 = entry - atr * 6
            return Signal(
                symbol=analysis["symbol"], strategy=self.name, direction="SHORT",
                entry=round(entry, 6), stop_loss=round(sl, 6),
                take_profit_1=round(tp1, 6), take_profit_2=round(tp2, 6),
                take_profit_3=round(tp3, 6), confidence=70.0, reasoning=reasoning,
            )
        return None
