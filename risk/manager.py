"""Trade gating for public signals.

Two flow profiles:
- standard: 4h swings on majors, min R/R 2.0, max-open 5
- quick:    5m scalps on volatiles, min R/R 1.2, max-open 4 (separate pool)

Dedupe is per-kind: a symbol can have one standard AND one quick trade
open at the same time, but not two of the same kind.
"""
from __future__ import annotations

from typing import Optional, Tuple
from sqlalchemy import select, func

from config import settings
from database import get_session, Trade
from strategies.base import Signal


# Quick-flow tunables — kept local because they're product decisions, not
# environment config.
QUICK_MIN_RR = 1.2
QUICK_MAX_OPEN = 4
QUICK_MIN_RISK_PCT = 0.2
QUICK_MAX_RISK_PCT = 8.0


class RiskManager:
    def __init__(self,
                 min_rr: Optional[float] = None,
                 max_open: Optional[int] = None) -> None:
        self.min_rr = min_rr or settings.min_risk_reward
        self.max_open = max_open or settings.max_open_trades

    @staticmethod
    def position_size(signal: Signal) -> Tuple[float, float]:
        if signal.entry <= 0:
            return 0.0, 0.0
        risk_pct = abs(signal.entry - signal.stop_loss) / signal.entry * 100.0
        return 1.0, round(risk_pct, 2)

    def open_trades_count(self, kind: str = "standard") -> int:
        with get_session() as s:
            return int(s.scalar(
                select(func.count(Trade.id)).where(
                    Trade.status == "open",
                    Trade.kind == kind,
                )
            ) or 0)

    def can_open(self, signal: Signal, kind: str = "standard") -> Tuple[bool, str]:
        if signal.entry <= 0 or signal.stop_loss <= 0:
            return False, "أسعار الدخول/وقف الخسارة غير صالحة"

        risk_pct = abs(signal.entry - signal.stop_loss) / signal.entry * 100.0

        if kind == "quick":
            if risk_pct < QUICK_MIN_RISK_PCT or risk_pct > QUICK_MAX_RISK_PCT:
                return False, f"مسافة وقف الخسارة غير منطقية للسريعة ({risk_pct:.2f}%)"
            if signal.risk_reward < QUICK_MIN_RR:
                return False, f"R/R = {signal.risk_reward} أقل من حد السريعة {QUICK_MIN_RR}"
            if self.open_trades_count(kind="quick") >= QUICK_MAX_OPEN:
                return False, f"عدد الصفقات السريعة المفتوحة بلغ الحد ({QUICK_MAX_OPEN})"
        else:
            if risk_pct < 0.3 or risk_pct > 15.0:
                return False, f"مسافة وقف الخسارة غير منطقية ({risk_pct:.2f}%)"
            if signal.risk_reward < self.min_rr:
                return False, f"R/R = {signal.risk_reward} أقل من الحد الأدنى {self.min_rr}"
            if self.open_trades_count(kind="standard") >= self.max_open:
                return False, f"عدد الصفقات المفتوحة بلغ الحد الأقصى ({self.max_open})"

        # de-dupe per kind: one symbol, one open trade per flow
        with get_session() as s:
            existing = s.scalar(select(func.count(Trade.id)).where(
                Trade.symbol == signal.symbol,
                Trade.status == "open",
                Trade.kind == kind,
            )) or 0
            if existing:
                label = "سريعة" if kind == "quick" else "مفتوحة"
                return False, f"يوجد صفقة {label} مسبقاً على {signal.symbol}"
        return True, "OK"
