from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from config import settings, WHITELIST, MEME_WHITELIST
from utils import logger
from database import get_session, Signal as DbSignal, Trade
from data import MarketDataService
from data.market_data import QUICK_TIMEFRAMES
from analysis import Analyzer
from strategies import ALL_STRATEGIES, QUICK_STRATEGIES
from risk import RiskManager
from ai_formatter import AIFormatter
from telegram_bot import ChannelPublisher
from reports.generator import ReportGenerator


# Standard flow
TRADE_MAX_DURATION_HOURS = 48
ANALYSIS_DEDUPE_HOURS = 6
# Quick flow
QUICK_TRADE_MAX_DURATION_MINUTES = 30
QUICK_SCAN_INTERVAL_MINUTES = 2


class JobOrchestrator:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone=settings.timezone)
        self.market = MarketDataService()
        self.analyzer = Analyzer(self.market)
        self.formatter = AIFormatter()
        self.publisher = ChannelPublisher()
        self.risk = RiskManager()
        self.reporter = ReportGenerator(self.formatter, self.publisher)
        self._published_analyses: dict[str, datetime] = {}

    def start(self) -> None:
        # Daily analyses (standard)
        self.scheduler.add_job(self.run_daily_analysis, CronTrigger(hour=8, minute=0),
                               id="analysis_morning", replace_existing=True)
        self.scheduler.add_job(self.run_daily_analysis, CronTrigger(hour=20, minute=0),
                               id="analysis_evening", replace_existing=True)

        # Standard strategy scan (4h flow)
        self.scheduler.add_job(self.scan_strategies, IntervalTrigger(minutes=5),
                               id="strategy_scan", replace_existing=True)

        # Quick scalp scan (5m flow on memes/volatiles)
        self.scheduler.add_job(self.scan_quick_strategies,
                               IntervalTrigger(minutes=QUICK_SCAN_INTERVAL_MINUTES),
                               id="quick_scan", replace_existing=True)

        # Open-trade monitoring & expiry (covers both kinds)
        self.scheduler.add_job(self.monitor_trades, IntervalTrigger(seconds=30),
                               id="trade_monitor", replace_existing=True)
        self.scheduler.add_job(self.expire_old_trades, IntervalTrigger(minutes=10),
                               id="trade_expiry", replace_existing=True)
        self.scheduler.add_job(self.expire_quick_trades, IntervalTrigger(minutes=1),
                               id="quick_expiry", replace_existing=True)

        # Reports
        self.scheduler.add_job(self.reporter.generate_weekly,
                               CronTrigger(day_of_week="sat", hour=18, minute=0),
                               id="weekly_report", replace_existing=True)
        self.scheduler.add_job(self.reporter.generate_monthly,
                               CronTrigger(day="last", hour=18, minute=0),
                               id="monthly_report", replace_existing=True)

        # Boot kick-off
        now = datetime.now(self.scheduler.timezone)
        self.scheduler.add_job(self.scan_strategies,
                               DateTrigger(run_date=now + timedelta(seconds=30)),
                               id="kickoff_scan", replace_existing=True)
        self.scheduler.add_job(self.scan_quick_strategies,
                               DateTrigger(run_date=now + timedelta(seconds=45)),
                               id="kickoff_quick_scan", replace_existing=True)

        self.scheduler.start()
        logger.info("scheduler started (standard + quick flows)")

    # ---------------- standard jobs ----------------
    async def run_daily_analysis(self) -> None:
        logger.info("running daily analysis")
        now = datetime.utcnow()
        for symbol in WHITELIST:
            try:
                last = self._published_analyses.get(symbol)
                if last and (now - last) < timedelta(hours=ANALYSIS_DEDUPE_HOURS):
                    continue
                payload = await asyncio.to_thread(self.analyzer.analyze, symbol, "4h")
                if not payload:
                    continue
                text = await asyncio.to_thread(self.formatter.format_analysis, payload)
                await self.publisher.publish_analysis(text)
                self._published_analyses[symbol] = datetime.utcnow()
                await asyncio.sleep(2)
            except Exception as e:
                logger.exception(f"analysis failed for {symbol}: {e}")

    async def scan_strategies(self) -> None:
        logger.debug("scanning standard strategies")
        for symbol in WHITELIST:
            try:
                payload = await asyncio.to_thread(self.analyzer.analyze, symbol, "4h")
                if not payload:
                    continue
                for strat in ALL_STRATEGIES:
                    sig = strat.evaluate(payload)
                    if not sig:
                        continue
                    handled = await self._handle_new_signal(sig, kind="standard")
                    if handled:
                        break
            except Exception as e:
                logger.exception(f"strategy scan failed for {symbol}: {e}")

    # ---------------- quick (scalp) jobs ----------------
    async def scan_quick_strategies(self) -> None:
        logger.debug("scanning quick strategies")
        for symbol in MEME_WHITELIST:
            try:
                payload = await asyncio.to_thread(
                    self.analyzer.analyze, symbol, "5m", QUICK_TIMEFRAMES
                )
                if not payload:
                    continue
                for strat in QUICK_STRATEGIES:
                    sig = strat.evaluate(payload)
                    if not sig:
                        continue
                    handled = await self._handle_new_signal(sig, kind="quick")
                    if handled:
                        break
            except Exception as e:
                logger.exception(f"quick scan failed for {symbol}: {e}")

    # ---------------- common signal handler ----------------
    async def _handle_new_signal(self, sig, kind: str = "standard") -> bool:
        ok, reason = self.risk.can_open(sig, kind=kind)
        if not ok:
            logger.info(f"signal rejected ({sig.symbol}/{sig.strategy}/{kind}): {reason}")
            return False
        size, risk_pct = self.risk.position_size(sig)
        entry_time = datetime.utcnow()

        with get_session() as s:
            db_sig = DbSignal(
                symbol=sig.symbol, strategy=sig.strategy, direction=sig.direction,
                kind=kind,
                entry=sig.entry, stop_loss=sig.stop_loss,
                take_profit_1=sig.take_profit_1, take_profit_2=sig.take_profit_2,
                take_profit_3=sig.take_profit_3, confidence=sig.confidence,
                risk_reward=sig.risk_reward, reasoning="\n".join(sig.reasoning),
                status="opened", created_at=entry_time,
            )
            s.add(db_sig)
            s.flush()
            signal_id = db_sig.id
            trade = Trade(
                signal_id=signal_id, symbol=sig.symbol, direction=sig.direction,
                kind=kind,
                entry_price=sig.entry, stop_loss=sig.stop_loss,
                take_profit_1=sig.take_profit_1, take_profit_2=sig.take_profit_2,
                take_profit_3=sig.take_profit_3, position_size=size, risk_usd=risk_pct,
                status="open", entry_time=entry_time,
            )
            s.add(trade)

        payload = sig.to_dict()
        payload["entry_time"] = entry_time
        payload["signal_id"] = signal_id
        payload["kind"] = kind
        text = await asyncio.to_thread(self.formatter.format_signal, payload)
        await self.publisher.publish_trade(text)
        tag = "QUICK" if kind == "quick" else "STD"
        logger.info(
            f"new {tag} trade opened: {sig.symbol} {sig.direction} "
            f"via {sig.strategy} [#ID{signal_id}]"
        )
        return True

    async def monitor_trades(self) -> None:
        with get_session() as s:
            rows = s.scalars(select(Trade).where(Trade.status == "open")).all()
            open_trades = [(t.id, t.symbol) for t in rows]

        for tid, symbol in open_trades:
            try:
                ticker = await asyncio.to_thread(self.market.get_ticker_snapshot, symbol)
                price = float(ticker["last"])
                await self._evaluate_trade(tid, price)
            except Exception as e:
                logger.exception(f"monitor failed for trade {tid}: {e}")

    async def expire_old_trades(self) -> None:
        cutoff = datetime.utcnow() - timedelta(hours=TRADE_MAX_DURATION_HOURS)
        with get_session() as s:
            rows = s.scalars(select(Trade).where(
                Trade.status == "open",
                Trade.kind == "standard",
                Trade.entry_time < cutoff,
            )).all()
            expired = [(t.id, t.symbol) for t in rows]
        for tid, symbol in expired:
            try:
                ticker = await asyncio.to_thread(self.market.get_ticker_snapshot, symbol)
                price = float(ticker["last"])
                await self._close_trade(tid, price, result="expired")
            except Exception as e:
                logger.exception(f"expire failed for trade {tid}: {e}")

    async def expire_quick_trades(self) -> None:
        cutoff = datetime.utcnow() - timedelta(minutes=QUICK_TRADE_MAX_DURATION_MINUTES)
        with get_session() as s:
            rows = s.scalars(select(Trade).where(
                Trade.status == "open",
                Trade.kind == "quick",
                Trade.entry_time < cutoff,
            )).all()
            expired = [(t.id, t.symbol) for t in rows]
        for tid, symbol in expired:
            try:
                ticker = await asyncio.to_thread(self.market.get_ticker_snapshot, symbol)
                price = float(ticker["last"])
                await self._close_trade(tid, price, result="expired")
            except Exception as e:
                logger.exception(f"quick expire failed for trade {tid}: {e}")

    async def _evaluate_trade(self, trade_id: int, price: float) -> None:
        close_payload: Optional[dict] = None

        with get_session() as s:
            t = s.get(Trade, trade_id)
            if not t or t.status != "open":
                return

            closed = False
            result: Optional[str] = None

            if t.direction == "LONG":
                if price <= t.stop_loss:
                    closed, result = True, "loss"
                elif price >= t.take_profit_3:
                    closed, result = True, "win"
                else:
                    if price >= t.take_profit_1 and not t.tp1_hit:
                        t.tp1_hit = True
                        t.stop_loss = t.entry_price  # break-even
                    if price >= t.take_profit_2 and not t.tp2_hit:
                        t.tp2_hit = True
            else:  # SHORT
                if price >= t.stop_loss:
                    closed, result = True, "loss"
                elif price <= t.take_profit_3:
                    closed, result = True, "win"
                else:
                    if price <= t.take_profit_1 and not t.tp1_hit:
                        t.tp1_hit = True
                        t.stop_loss = t.entry_price
                    if price <= t.take_profit_2 and not t.tp2_hit:
                        t.tp2_hit = True

            if closed:
                t.status = "closed"
                t.exit_price = price
                t.exit_time = datetime.utcnow()
                if t.direction == "LONG":
                    t.pnl_percent = (price - t.entry_price) / t.entry_price * 100
                else:
                    t.pnl_percent = (t.entry_price - price) / t.entry_price * 100
                t.pnl_usd = 0.0
                t.result = result
                close_payload = self._build_close_payload(t)

        if close_payload:
            await self._publish_close(close_payload)

    async def _close_trade(self, trade_id: int, price: float, result: str) -> None:
        close_payload: Optional[dict] = None
        with get_session() as s:
            t = s.get(Trade, trade_id)
            if not t or t.status != "open":
                return
            t.status = "closed"
            t.exit_price = price
            t.exit_time = datetime.utcnow()
            if t.direction == "LONG":
                t.pnl_percent = (price - t.entry_price) / t.entry_price * 100
            else:
                t.pnl_percent = (t.entry_price - price) / t.entry_price * 100
            t.pnl_usd = 0.0
            t.result = result
            close_payload = self._build_close_payload(t)
        if close_payload:
            await self._publish_close(close_payload)

    def _build_close_payload(self, t: Trade) -> dict:
        duration = "—"
        if t.entry_time and t.exit_time:
            secs = int((t.exit_time - t.entry_time).total_seconds())
            if secs < 3600:
                duration = f"{secs // 60}د"
            else:
                h, rem = divmod(secs, 3600)
                m = rem // 60
                duration = f"{h}س {m}د"
        return {
            "signal_id": t.signal_id,
            "symbol": t.symbol,
            "direction": t.direction,
            "kind": t.kind,
            "entry_price": t.entry_price,
            "exit_price": t.exit_price,
            "pnl_percent": round(t.pnl_percent or 0.0, 2),
            "result": t.result,
            "duration": duration,
            "tp1_hit": bool(t.tp1_hit),
            "tp2_hit": bool(t.tp2_hit),
            "tp3_hit": bool(t.tp3_hit),
        }

    async def _publish_close(self, payload: dict) -> None:
        text = await asyncio.to_thread(self.formatter.format_trade_close, payload)
        await self.publisher.publish_trade(text)
        tag = "QUICK" if payload.get("kind") == "quick" else "STD"
        logger.info(
            f"{tag} trade closed: {payload['symbol']} {payload['direction']} "
            f"[#ID{payload.get('signal_id')}] result={payload['result']} pnl={payload['pnl_percent']}%"
        )
