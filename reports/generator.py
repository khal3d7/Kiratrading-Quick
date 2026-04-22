from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from sqlalchemy import select, func

from utils import logger
from database import get_session, Trade, Report
from ai_formatter import AIFormatter
from telegram_bot import ChannelPublisher


class ReportGenerator:
    def __init__(self, formatter: AIFormatter, publisher: ChannelPublisher) -> None:
        self.formatter = formatter
        self.publisher = publisher

    async def generate_weekly(self) -> None:
        await self._generate(period="weekly", days=7)

    async def generate_monthly(self) -> None:
        await self._generate(period="monthly", days=30)

    async def _generate(self, period: str, days: int) -> None:
        since = datetime.utcnow() - timedelta(days=days)
        with get_session() as s:
            rows = s.scalars(
                select(Trade).where(Trade.entry_time >= since, Trade.status == "closed")
            ).all()
            total = len(rows)
            wins = sum(1 for t in rows if t.result == "win")
            losses = sum(1 for t in rows if t.result == "loss")
            pnl_usd = sum((t.pnl_usd or 0) for t in rows)
            avg_pct = (sum((t.pnl_percent or 0) for t in rows) / total) if total else 0
            stats = {
                "period": period,
                "since": since.isoformat(),
                "total": total, "wins": wins, "losses": losses,
                "win_rate": round((wins / (wins + losses) * 100) if (wins + losses) else 0, 2),
                "pnl_usd": round(pnl_usd, 2),
                "avg_pct_per_trade": round(avg_pct, 2),
            }
            summary = self._format_report(stats, period)
            s.add(Report(period=period, summary=summary, stats_json=stats))

        await self.publisher.publish_analysis(summary)
        logger.info(f"{period} report published")

    def _format_report(self, stats: dict, period: str) -> str:
        title = "📅 *التقرير الأسبوعي*" if period == "weekly" else "📆 *التقرير الشهري*"
        return (
            f"{title}\n\n"
            f"إجمالي الصفقات: {stats['total']}\n"
            f"الناجحة: {stats['wins']} ✅\n"
            f"الخاسرة: {stats['losses']} ❌\n"
            f"نسبة النجاح: {stats['win_rate']}%\n"
            f"إجمالي الربح/الخسارة: {stats['pnl_usd']} $\n"
            f"متوسط الربح/الصفقة: {stats['avg_pct_per_trade']}%\n"
        )
