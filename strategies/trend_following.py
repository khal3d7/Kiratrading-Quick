from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseStrategy, Signal


class TrendFollowingStrategy(BaseStrategy):
    name = "Trend Following (EMA50/200 + ADX)"

    def evaluate(self, analysis: Dict[str, Any]) -> Optional[Signal]:
        ind = analysis["indicators"].get("4h", {})
        ind_d = analysis["indicators"].get("1d", {})
        if not ind or not ind_d:
            return None

        price = ind.get("price")
        ema50 = ind.get("ema_50")
        ema200 = ind.get("ema_200") or ind_d.get("ema_200")
        adx = ind.get("adx_14") or 0
        macd = ind.get("macd") or 0
        macd_sig = ind.get("macd_signal") or 0
        atr = ind.get("atr_14") or 0
        if not (price and ema50 and ema200 and atr):
            return None

        reasoning = []
        if ema50 > ema200 and price > ema50 and adx > 25 and macd > macd_sig:
            reasoning.append(f"EMA50 ({ema50:.2f}) فوق EMA200 ({ema200:.2f}) — اتجاه صاعد")
            reasoning.append(f"ADX = {adx:.1f} > 25 — قوة اتجاه")
            reasoning.append("MACD فوق خط الإشارة")
            sl = price - atr * 1.5
            tp1 = price + atr * 2
            tp2 = price + atr * 4
            tp3 = price + atr * 6
            confidence = min(95.0, 50 + adx)
            return Signal(
                symbol=analysis["symbol"],
                strategy=self.name,
                direction="LONG",
                entry=round(price, 6),
                stop_loss=round(sl, 6),
                take_profit_1=round(tp1, 6),
                take_profit_2=round(tp2, 6),
                take_profit_3=round(tp3, 6),
                confidence=round(confidence, 1),
                reasoning=reasoning,
            )

        if ema50 < ema200 and price < ema50 and adx > 25 and macd < macd_sig:
            reasoning.append(f"EMA50 ({ema50:.2f}) تحت EMA200 ({ema200:.2f}) — اتجاه هابط")
            reasoning.append(f"ADX = {adx:.1f} > 25 — قوة اتجاه")
            reasoning.append("MACD تحت خط الإشارة")
            sl = price + atr * 1.5
            tp1 = price - atr * 2
            tp2 = price - atr * 4
            tp3 = price - atr * 6
            confidence = min(95.0, 50 + adx)
            return Signal(
                symbol=analysis["symbol"],
                strategy=self.name,
                direction="SHORT",
                entry=round(price, 6),
                stop_loss=round(sl, 6),
                take_profit_1=round(tp1, 6),
                take_profit_2=round(tp2, 6),
                take_profit_3=round(tp3, 6),
                confidence=round(confidence, 1),
                reasoning=reasoning,
            )
        return None
