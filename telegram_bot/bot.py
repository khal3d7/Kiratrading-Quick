from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, desc, func

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes,
)

from config import settings
from utils import logger
from database import get_session, Trade, Signal as DbSignal
from data import MarketDataService
from .keyboards import main_menu, back_menu, pagination


PAGE_SIZE = 6


def _f(v, digits: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        if abs(v) >= 1000:
            return f"{v:,.2f}"
        return f"{v:,.{digits}f}"
    return str(v)


def _pct(a: float, b: float) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return (a - b) / b * 100.0


def _pf(v: Optional[float]) -> str:
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _fmt_dt(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "—"


def _duration(start: Optional[datetime], end: Optional[datetime]) -> str:
    if not start or not end:
        return "—"
    secs = int((end - start).total_seconds())
    if secs < 3600:
        return f"{secs // 60}د"
    h, rem = divmod(secs, 3600)
    m = rem // 60
    if h >= 24:
        d, h2 = divmod(h, 24)
        return f"{d}ي {h2}س {m}د"
    return f"{h}س {m}د"


def _result_badge(result: Optional[str], status: str) -> str:
    if status == "open":
        return "🟡 مفتوحة"
    return {
        "win": "✅ ربح",
        "loss": "❌ خسارة",
        "expired": "⌛ انتهاء مدة",
        "breakeven": "⚪ متعادل",
    }.get(result or "", "—")


def _kind_emoji(kind: Optional[str]) -> str:
    return "⚡" if kind == "quick" else "🧠"


class TradingBot:
    def __init__(self) -> None:
        self.app: Optional[Application] = None
        self.market = MarketDataService()

    def build(self) -> Application:
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
        self.app = ApplicationBuilder().token(settings.telegram_bot_token).build()
        self.app.add_handler(CommandHandler("start", self._cmd_start))
        self.app.add_handler(CommandHandler("menu", self._cmd_start))
        self.app.add_handler(CommandHandler("status", self._cmd_status))
        self.app.add_handler(CommandHandler("trades", self._cmd_trades))
        self.app.add_handler(CommandHandler("history", self._cmd_history))
        self.app.add_handler(CommandHandler("quick", self._cmd_quick))
        self.app.add_handler(CallbackQueryHandler(self._on_callback))
        return self.app

    # -------- commands (open to all members) --------
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        await update.message.reply_text(
            f"👋 أهلاً <b>{user.first_name}</b>!\n"
            "مرحباً بك في لوحة تحكم إشارات التداول.\n\n"
            "🧠 <b>الصفقات الذكية</b> — مدى متوسط/طويل على عملات الميجور (4س)\n"
            "⚡ <b>الصفقات السريعة</b> — سكالب 5د على العملات المتقلبة (15-30د)\n\n"
            "اختر من القائمة بالأسفل:",
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        with get_session() as s:
            std_open = int(s.scalar(select(func.count(Trade.id)).where(
                Trade.status == "open", Trade.kind == "standard")) or 0)
            qk_open = int(s.scalar(select(func.count(Trade.id)).where(
                Trade.status == "open", Trade.kind == "quick")) or 0)
            closed_n = int(s.scalar(select(func.count(Trade.id)).where(
                Trade.status == "closed")) or 0)
        await update.message.reply_text(
            f"النظام يعمل ✅\n"
            f"🧠 صفقات ذكية مفتوحة: <b>{std_open}</b>\n"
            f"⚡ صفقات سريعة مفتوحة: <b>{qk_open}</b>\n"
            f"📜 صفقات مغلقة: <b>{closed_n}</b>",
            parse_mode=ParseMode.HTML,
        )

    async def _cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text, kb = self._render_trade_list(status="open", page=0, kind="standard")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    async def _cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text, kb = self._render_trade_list(status="closed", page=0, kind=None)
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    async def _cmd_quick(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text, kb = self._render_trade_list(status="open", page=0, kind="quick")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    # -------- callback router --------
    async def _on_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        q = update.callback_query
        await q.answer()
        data = q.data or ""

        if data == "menu":
            await q.edit_message_text("القائمة الرئيسية:", reply_markup=main_menu())
            return

        if data == "stats":
            await self._show_stats(q); return
        if data == "report":
            await self._show_report(q); return
        if data == "settings":
            await self._show_settings(q); return
        if data == "notifications":
            await q.edit_message_text(
                "🔔 الإشعارات تُرسَل تلقائياً إلى قنوات التحليل والصفقات.",
                reply_markup=back_menu(),
            )
            return

        # Quick-flow shortcuts
        if data == "quick:open":
            text, kb = self._render_trade_list(status="open", page=0, kind="quick")
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb); return
        if data == "quick:closed":
            text, kb = self._render_trade_list(status="closed", page=0, kind="quick")
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb); return

        if data.startswith("klist:"):
            # klist:<kind>:<status>:<page>
            _, kind, status, page = data.split(":")
            kind_arg = None if kind == "all" else kind
            text, kb = self._render_trade_list(status=status, page=int(page), kind=kind_arg)
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
            return

        if data.startswith("list:"):
            _, status, page = data.split(":")
            text, kb = self._render_trade_list(status=status, page=int(page), kind="standard")
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
            return

        if data.startswith("trade:"):
            tid = int(data.split(":", 1)[1])
            text, kb = await self._render_trade_detail(tid)
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb,
                                      disable_web_page_preview=True)
            return

        # legacy menu items
        if data == "trades:open":
            text, kb = self._render_trade_list(status="open", page=0, kind="standard")
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb); return
        if data == "trades:closed":
            text, kb = self._render_trade_list(status="closed", page=0, kind="standard")
            await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb); return
        if data == "trades:new":
            await self._show_recent_signals(q); return

    # -------- views --------
    def _render_trade_list(self, status: str, page: int, kind: Optional[str] = None):
        if kind == "quick":
            head = "⚡ <b>الصفقات السريعة الجارية</b>" if status == "open" \
                else "⚡ <b>سجل الصفقات السريعة</b>"
        elif kind == "standard":
            head = "🧠 <b>الصفقات الذكية الجارية</b>" if status == "open" \
                else "🧠 <b>سجل الصفقات الذكية</b>"
        else:
            head = "🔄 <b>كل الصفقات الجارية</b>" if status == "open" \
                else "✅ <b>كل الصفقات المنتهية</b>"

        with get_session() as s:
            base = select(Trade).where(Trade.status == status)
            count_base = select(func.count(Trade.id)).where(Trade.status == status)
            if kind:
                base = base.where(Trade.kind == kind)
                count_base = count_base.where(Trade.kind == kind)
            total = int(s.scalar(count_base) or 0)
            rows = s.scalars(
                base.order_by(desc(Trade.entry_time))
                .offset(page * PAGE_SIZE).limit(PAGE_SIZE)
            ).all()
            items = [
                (t.id, t.symbol, t.direction, t.entry_price, t.pnl_percent,
                 t.result, t.entry_time, t.exit_time, t.kind)
                for t in rows
            ]

        kind_key = kind or "all"
        if not items:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ القائمة", callback_data="menu")]
            ])
            return f"{head}\n\nلا توجد بيانات بعد.", kb

        lines = [head, "━━━━━━━━━━━━━━━",
                 f"المجموع: <b>{total}</b>   ·   صفحة <b>{page+1}</b>", ""]
        buttons: List[List[InlineKeyboardButton]] = []
        for tid, sym, direction, entry, pnl, result, et, xt, k in items:
            arrow = "🟢" if direction == "LONG" else "🔴"
            kemoji = _kind_emoji(k)
            tag = (_pf(pnl) if status == "closed"
                   else f"دخول {_f(entry)}")
            badge = _result_badge(result, status)
            when = _fmt_dt(xt if status == "closed" else et)
            lines.append(
                f"{arrow}{kemoji} <b>#{tid}</b>  <code>{sym}</code>  {direction}  ·  {tag}\n"
                f"     {badge}  ·  {when}"
            )
            buttons.append([InlineKeyboardButton(
                f"{arrow}{kemoji} #{tid} {sym} ({tag})",
                callback_data=f"trade:{tid}",
            )])

        nav: List[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(
                "◀️ السابق", callback_data=f"klist:{kind_key}:{status}:{page-1}"))
        if (page + 1) * PAGE_SIZE < total:
            nav.append(InlineKeyboardButton(
                "التالي ▶️", callback_data=f"klist:{kind_key}:{status}:{page+1}"))
        if nav:
            buttons.append(nav)

        # cross-link row depending on context
        if kind == "quick":
            buttons.append([
                InlineKeyboardButton(
                    "⚡ السجل" if status == "open" else "⚡ الجارية",
                    callback_data=f"klist:quick:{'closed' if status=='open' else 'open'}:0"),
                InlineKeyboardButton("🧠 الذكية", callback_data="klist:standard:open:0"),
            ])
        elif kind == "standard":
            buttons.append([
                InlineKeyboardButton(
                    "✅ المنتهية" if status == "open" else "🔄 الجارية",
                    callback_data=f"klist:standard:{'closed' if status=='open' else 'open'}:0"),
                InlineKeyboardButton("⚡ السريعة", callback_data="klist:quick:open:0"),
            ])
        else:
            buttons.append([
                InlineKeyboardButton("🧠 الذكية", callback_data="klist:standard:open:0"),
                InlineKeyboardButton("⚡ السريعة", callback_data="klist:quick:open:0"),
            ])
        buttons.append([InlineKeyboardButton("⬅️ القائمة", callback_data="menu")])

        return "\n".join(lines), InlineKeyboardMarkup(buttons)

    async def _render_trade_detail(self, tid: int):
        with get_session() as s:
            t = s.get(Trade, tid)
            if not t:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ القائمة", callback_data="menu")]])
                return "لم يتم العثور على الصفقة.", kb
            sig = s.get(DbSignal, t.signal_id) if t.signal_id else None
            d = {
                "id": t.id, "signal_id": t.signal_id,
                "symbol": t.symbol, "direction": t.direction, "kind": t.kind,
                "entry_price": t.entry_price, "stop_loss": t.stop_loss,
                "tp1": t.take_profit_1, "tp2": t.take_profit_2, "tp3": t.take_profit_3,
                "tp1_hit": bool(t.tp1_hit), "tp2_hit": bool(t.tp2_hit), "tp3_hit": bool(t.tp3_hit),
                "status": t.status, "result": t.result,
                "exit_price": t.exit_price, "pnl_percent": t.pnl_percent,
                "entry_time": t.entry_time, "exit_time": t.exit_time,
                "strategy": sig.strategy if sig else "—",
                "confidence": sig.confidence if sig else None,
                "risk_reward": sig.risk_reward if sig else None,
                "reasoning": sig.reasoning if sig and sig.reasoning else "",
            }

        now_price = d["exit_price"]
        if d["status"] == "open":
            try:
                ticker = self.market.get_ticker_snapshot(d["symbol"])
                now_price = float(ticker.get("last") or 0) or None
            except Exception as e:
                logger.warning(f"detail: live price fetch failed for {d['symbol']}: {e}")
                now_price = None

        live_pnl = _pct(now_price, d["entry_price"]) if d["status"] == "open" and now_price else d["pnl_percent"]
        if d["direction"] == "SHORT" and live_pnl is not None:
            live_pnl = -live_pnl

        sl_pct = _pct(d["stop_loss"], d["entry_price"])
        tp1_pct = _pct(d["tp1"], d["entry_price"])
        tp2_pct = _pct(d["tp2"], d["entry_price"])
        tp3_pct = _pct(d["tp3"], d["entry_price"])

        arrow = "🟢" if d["direction"] == "LONG" else "🔴"
        kemoji = _kind_emoji(d["kind"])
        kind_label = "صفقة سريعة ⚡" if d["kind"] == "quick" else "صفقة ذكية 🧠"
        end_time = d["exit_time"] or datetime.utcnow()
        dur = _duration(d["entry_time"], end_time)
        badge = _result_badge(d["result"], d["status"])

        def chk(b): return "✅" if b else "▫️"

        lines = [
            f"{kemoji} <b>تفاصيل {kind_label} #{d['id']}</b>",
            "━━━━━━━━━━━━━━━",
            f"{arrow} <b>{d['symbol']}</b> · {d['direction']}",
            f"🧠 الاستراتيجية: {d['strategy']}",
            f"📊 الحالة: {badge}",
            "",
            f"💵 سعر الدخول: <b>{_f(d['entry_price'])}</b>",
            (f"💰 السعر الحالي: <b>{_f(now_price)}</b>   ({_pf(live_pnl)})"
             if d["status"] == "open"
             else f"💰 سعر الإغلاق: <b>{_f(now_price)}</b>   (<b>{_pf(d['pnl_percent'])}</b>)"),
            f"🛑 وقف الخسارة: {_f(d['stop_loss'])}   ({_pf(sl_pct)})",
            "",
            "🎯 <b>الأهداف:</b>",
            f"   {chk(d['tp1_hit'])} TP1: {_f(d['tp1'])}   ({_pf(tp1_pct)})",
            f"   {chk(d['tp2_hit'])} TP2: {_f(d['tp2'])}   ({_pf(tp2_pct)})",
            f"   {chk(d['tp3_hit'])} TP3: {_f(d['tp3'])}   ({_pf(tp3_pct)})",
            "",
            f"⚖️ R/R: <b>1 : {_f(d['risk_reward'], 2)}</b>"
            f"   ·   📊 الثقة: <b>{_f(d['confidence'], 0)}%</b>",
            "",
            f"🕒 الدخول: {_fmt_dt(d['entry_time'])}",
            (f"🕒 الإغلاق: {_fmt_dt(d['exit_time'])}" if d["status"] == "closed"
             else f"⏱️ مفتوحة منذ: {dur}"),
            (f"⏱️ المدة: {dur}" if d["status"] == "closed" else ""),
        ]
        if d["reasoning"]:
            lines += ["", "<b>💡 أسباب الإشارة:</b>"]
            for r in [x for x in d["reasoning"].split("\n") if x.strip()][:5]:
                lines.append(f"• {r.strip()}")

        back_kind = d["kind"] or "standard"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 تحديث", callback_data=f"trade:{tid}")],
            [InlineKeyboardButton("🔄 الجارية", callback_data=f"klist:{back_kind}:open:0"),
             InlineKeyboardButton("✅ السجل", callback_data=f"klist:{back_kind}:closed:0")],
            [InlineKeyboardButton("⬅️ القائمة", callback_data="menu")],
        ])
        return "\n".join([l for l in lines if l != ""]).replace("\n\n\n", "\n\n"), kb

    async def _show_recent_signals(self, q) -> None:
        with get_session() as s:
            rows = s.scalars(
                select(DbSignal).order_by(desc(DbSignal.created_at)).limit(8)
            ).all()
            items = [(r.id, r.symbol, r.direction, r.strategy, r.entry,
                      r.risk_reward, r.confidence, r.created_at, r.kind) for r in rows]
        if not items:
            await q.edit_message_text("لا توجد إشارات بعد.", reply_markup=back_menu()); return
        lines = ["🆕 <b>أحدث الإشارات</b>", "━━━━━━━━━━━━━━━"]
        for sid, sym, dr, strat, entry, rr, conf, ct, k in items:
            arrow = "🟢" if dr == "LONG" else "🔴"
            kemoji = _kind_emoji(k)
            lines.append(
                f"{arrow}{kemoji} <b>#{sid}</b> <code>{sym}</code> {dr} · {strat}\n"
                f"    دخول {_f(entry)}  ·  R/R 1:{_f(rr,2)}  ·  ثقة {_f(conf,0)}%  ·  {_fmt_dt(ct)}"
            )
        await q.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=back_menu())

    async def _show_stats(self, q) -> None:
        def _stats_for(kind: Optional[str]):
            with get_session() as s:
                base = select(Trade)
                if kind:
                    base = base.where(Trade.kind == kind)
                count = lambda cond: int(s.scalar(  # noqa: E731
                    select(func.count(Trade.id)).where(*cond)
                ) or 0)
                k_filter = [Trade.kind == kind] if kind else []
                total = count(k_filter)
                closed = count([Trade.status == "closed", *k_filter])
                wins = count([Trade.result == "win", *k_filter])
                losses = count([Trade.result == "loss", *k_filter])
                expired = count([Trade.result == "expired", *k_filter])
                avg_pnl = float(s.scalar(
                    select(func.coalesce(func.avg(Trade.pnl_percent), 0.0)).where(
                        Trade.status == "closed", *k_filter)) or 0.0)
                sum_pnl = float(s.scalar(
                    select(func.coalesce(func.sum(Trade.pnl_percent), 0.0)).where(
                        Trade.status == "closed", *k_filter)) or 0.0)
                best = float(s.scalar(
                    select(func.coalesce(func.max(Trade.pnl_percent), 0.0)).where(
                        Trade.status == "closed", *k_filter)) or 0.0)
                worst = float(s.scalar(
                    select(func.coalesce(func.min(Trade.pnl_percent), 0.0)).where(
                        Trade.status == "closed", *k_filter)) or 0.0)
            decisive = wins + losses
            wr = (wins / decisive * 100.0) if decisive else 0.0
            return total, closed, wins, losses, expired, wr, avg_pnl, sum_pnl, best, worst

        std = _stats_for("standard")
        qk = _stats_for("quick")

        def _block(title, s):
            t, cl, w, l, ex, wr, avg, sm, bst, wst = s
            return (
                f"<b>{title}</b>\n"
                f"إجمالي: <b>{t}</b>  ·  مغلقة: <b>{cl}</b>\n"
                f"   ✅ {w}    ❌ {l}    ⌛ {ex}    📈 نسبة نجاح: <b>{wr:.1f}%</b>\n"
                f"متوسط: {_pf(avg)}  ·  تراكمي: {_pf(sm)}\n"
                f"🏆 {_pf(bst)}   📉 {_pf(wst)}"
            )

        text = (
            "📊 <b>إحصائيات الأداء</b>\n"
            "━━━━━━━━━━━━━━━\n"
            + _block("🧠 الصفقات الذكية", std)
            + "\n\n"
            + _block("⚡ الصفقات السريعة", qk)
            + "\n\n"
            "<i>كل النتائج محسوبة بالنسبة المئوية وقابلة للتطبيق على أي حجم رأس مال.</i>"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_menu())

    async def _show_report(self, q) -> None:
        text = (
            "📈 <b>تقارير الأداء</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "تُنشَر التقارير الأسبوعية والشهرية تلقائياً في قناة التحليل.\n"
            "للحصول على إحصائيات لحظية، استخدم زر <b>📊 الإحصائيات</b>."
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_menu())

    async def _show_settings(self, q) -> None:
        text = (
            "⚙️ <b>إعدادات النظام</b>\n"
            "━━━━━━━━━━━━━━━\n"
            f"المنصة: <b>{settings.exchange_id.upper()}</b>\n"
            "\n"
            "<b>🧠 المسار الذكي</b>\n"
            f"الإطار الأساسي: 4س  ·  R/R أدنى: 1:{settings.min_risk_reward}\n"
            f"حد الصفقات المفتوحة: {settings.max_open_trades}  ·  أقصى مدة: 48س\n"
            "\n"
            "<b>⚡ المسار السريع</b>\n"
            "الإطار الأساسي: 5د  ·  R/R أدنى: 1:1.2\n"
            "حد الصفقات المفتوحة: 4  ·  أقصى مدة: 30د\n"
            "\n"
            f"المنطقة الزمنية: <b>{settings.timezone}</b>\n"
            "\n"
            "<i>هذا بوت إشارات عام — لا يوجد رأس مال مُدار، ويمكن لكل متابع "
            "تطبيق الإشارة بالحجم المناسب له.</i>"
        )
        await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_menu())
