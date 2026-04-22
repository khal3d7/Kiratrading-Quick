"""Formats analysis JSON into Arabic Telegram messages.

Public-facing signals: percentages only, never invented numbers, never USD
position sizes. The LLM is used to enrich the *narrative* parts only — all
numeric fields are templated locally so they cannot be hallucinated.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from config import settings
from utils import logger


SYSTEM_PROMPT = (
    "أنت محرّر إشارات تداول للجمهور بالعربية الفصحى المختصرة. "
    "مهمتك صياغة فقرة موجزة تشرح السياق فقط بناءً على البيانات المعطاة. "
    "ممنوع منعاً باتاً اختراع أي رقم أو سعر أو نسبة. لا تذكر أي عملة غير "
    "المذكورة. أعد فقط النص العربي بدون أي علامات Markdown."
)


def _pct(a: float, b: float) -> Optional[float]:
    if a is None or b is None or b == 0:
        return None
    return (a - b) / b * 100.0


def _f(v, digits: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        if abs(v) >= 1000:
            return f"{v:,.2f}"
        return f"{v:,.{digits}f}"
    return str(v)


def _pf(v: Optional[float]) -> str:
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _tag(symbol: str) -> str:
    return "#" + symbol.replace("/", "").replace("-", "")


class AIFormatter:
    def __init__(self) -> None:
        self.provider = settings.ai_provider
        self.client = None
        if not settings.has_ai:
            logger.warning("AI keys not configured — using template formatter")
            return
        try:
            if self.provider == "openai":
                from openai import OpenAI
                self.client = OpenAI(api_key=settings.openai_api_key)
            elif self.provider == "anthropic":
                from anthropic import Anthropic
                self.client = Anthropic(api_key=settings.anthropic_api_key)
            elif self.provider == "gemini":
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=settings.gemini_api_key,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                )
        except Exception as e:
            logger.error(f"failed to init AI client: {e}")
            self.client = None

    # ---------------- public ----------------
    def format_analysis(self, payload: Dict[str, Any]) -> str:
        """Renders the analysis card. Numbers are templated locally; the LLM
        only writes the short narrative paragraph at the bottom."""
        return self._render_analysis(payload, narrative=self._narrative_for_analysis(payload))

    def format_signal(self, data: Dict[str, Any]) -> str:
        """Renders the signal card. `data` must include the keys produced by
        `Signal.to_dict()` plus optional `entry_time` and `signal_id`."""
        return self._render_signal(data, narrative=self._narrative_for_signal(data))

    def format_trade_close(self, data: Dict[str, Any]) -> str:
        return self._render_close(data)

    # ---------------- LLM narratives ----------------
    def _narrative_for_analysis(self, payload: Dict[str, Any]) -> str:
        compact = self._compact_analysis(payload)
        prompt = (
            "اكتب فقرة عربية واحدة موجزة (سطرين كحد أقصى) تلخّص حالة العملة "
            "وتوقعات الاتجاه القريب اعتماداً على هذه البيانات فقط. لا تذكر "
            "أي أرقام في الفقرة:\n"
            f"```json\n{json.dumps(compact, ensure_ascii=False)}\n```"
        )
        return self._ask_llm(prompt) or ""

    def _narrative_for_signal(self, data: Dict[str, Any]) -> str:
        prompt = (
            "اكتب جملة عربية واحدة (سطر) تشرح منطق الدخول لهذه الصفقة بناءً "
            "على الأسباب المعطاة، بدون ذكر أي رقم:\n"
            f"الاتجاه: {data.get('direction')}, الاستراتيجية: {data.get('strategy')}, "
            f"الأسباب: {data.get('reasoning')}"
        )
        return self._ask_llm(prompt) or ""

    def _ask_llm(self, prompt: str) -> Optional[str]:
        if not self.client:
            return None
        try:
            if self.provider in ("openai", "gemini"):
                model = settings.openai_model if self.provider == "openai" else settings.gemini_model
                resp = self.client.chat.completions.create(
                    model=model, temperature=0.3,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
                return (resp.choices[0].message.content or "").strip()
            if self.provider == "anthropic":
                resp = self.client.messages.create(
                    model=settings.anthropic_model, max_tokens=400, temperature=0.3,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                return (resp.content[0].text or "").strip()
        except Exception as e:
            logger.warning(f"LLM narrative skipped: {e}")
            return None

    # ---------------- templates ----------------
    def _render_analysis(self, p: Dict[str, Any], narrative: str = "") -> str:
        c = self._compact_analysis(p)
        ticker = c.get("ticker") or {}
        ind = c.get("indicators") or {}
        liq = c.get("liquidity") or {}
        last = ticker.get("last")
        chg = ticker.get("change_24h_pct")
        rsi = ind.get("rsi_14")
        rsi_lbl = ""
        if isinstance(rsi, (int, float)):
            rsi_lbl = " (تشبّع شراء)" if rsi >= 70 else " (تشبّع بيع)" if rsi <= 30 else ""
        trend = c.get("market_structure") or "محايد"
        trend_emoji = {"bullish": "📈", "bearish": "📉", "neutral": "➖"}.get(str(trend).lower(), "➖")
        ema50, ema200 = ind.get("ema_50"), ind.get("ema_200")
        bias = "—"
        if isinstance(ema50, (int, float)) and isinstance(ema200, (int, float)):
            bias = "صاعد" if ema50 > ema200 else "هابط"

        sup = c.get("support") or []
        res = c.get("resistance") or []

        lines = [
            f"📊 <b>تحليل {c.get('symbol')}</b> · الإطار {c.get('timeframe')}",
            "━━━━━━━━━━━━━━━",
            f"💰 السعر: <b>{_f(last)}</b>   ({_pf(chg)} 24س)",
            f"{trend_emoji} هيكل السوق: <b>{trend}</b>   |   تحيّز EMA: {bias}",
            "",
            "<b>المؤشرات الفنية:</b>",
            f"• RSI(14): {_f(rsi, 2)}{rsi_lbl}",
            f"• MACD: {_f(ind.get('macd'), 4)} / إشارة {_f(ind.get('macd_signal'), 4)}",
            f"• EMA50/200: {_f(ema50)} / {_f(ema200)}",
            f"• ADX(14): {_f(ind.get('adx_14'), 2)}   ATR: {_f(ind.get('atr_14'))}",
            f"• حجم/متوسط: {_f(ind.get('volume_ratio'), 2)}x",
            "",
            f"🟢 الدعوم: {', '.join(_f(x) for x in sup[:3]) or '—'}",
            f"🔴 المقاومات: {', '.join(_f(x) for x in res[:3]) or '—'}",
            f"💧 سيولة الكتاب: {_f(liq.get('total_liquidity_usd'), 0)} USD",
        ]
        if narrative:
            lines += ["", f"🧠 <i>{narrative}</i>"]
        lines += [
            "━━━━━━━━━━━━━━━",
            f"{_tag(c.get('symbol',''))} #تحليل_فني",
        ]
        return "\n".join(lines)

    def _render_signal(self, d: Dict[str, Any], narrative: str = "") -> str:
        direction = d.get("direction", "LONG")
        is_long = direction == "LONG"
        head_emoji = "🟢" if is_long else "🔴"
        kind = d.get("kind") or "standard"
        is_quick = kind == "quick"
        kind_emoji = "⚡" if is_quick else ""
        kind_label = " (سريعة)" if is_quick else ""
        head_label = ("إشارة شراء" if is_long else "إشارة بيع") + kind_label
        entry = d.get("entry")
        sl = d.get("stop_loss")
        tp1, tp2, tp3 = d.get("take_profit_1"), d.get("take_profit_2"), d.get("take_profit_3")
        sl_pct = _pct(sl, entry)
        tp1_pct = _pct(tp1, entry)
        tp2_pct = _pct(tp2, entry)
        tp3_pct = _pct(tp3, entry)

        ts = d.get("entry_time")
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%Y-%m-%d %H:%M") + " (Riyadh)"
        elif ts:
            ts_str = str(ts)
        else:
            ts_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M") + " UTC"

        sid = d.get("signal_id")
        title = f"{head_emoji}{kind_emoji} <b>{head_label} | {direction}</b>"
        if sid is not None:
            title += f"  · #ID{sid}"

        lines = [
            title,
            "━━━━━━━━━━━━━━━",
            f"🪙 العملة: <b>{d.get('symbol')}</b>",
            f"🧠 الاستراتيجية: {d.get('strategy')}",
            f"📊 درجة الثقة: <b>{_f(d.get('confidence'), 0)}%</b>",
            "",
            f"💵 الدخول: <b>{_f(entry)}</b>",
            f"🛑 وقف الخسارة: <b>{_f(sl)}</b>   ({_pf(sl_pct)})",
            f"🎯 الهدف 1: {_f(tp1)}   ({_pf(tp1_pct)})",
            f"🎯 الهدف 2: {_f(tp2)}   ({_pf(tp2_pct)})",
            f"🎯 الهدف 3: {_f(tp3)}   ({_pf(tp3_pct)})",
            "",
            f"⚖️ المخاطرة/الربح: <b>1 : {_f(d.get('risk_reward'), 2)}</b>",
            f"🕒 وقت الدخول: {ts_str}",
        ]
        reasons = d.get("reasoning") or []
        if reasons:
            lines += ["", "<b>💡 أسباب الإشارة:</b>"]
            for r in reasons[:5]:
                lines.append(f"• {r}")
        if narrative:
            lines += ["", f"🧠 <i>{narrative}</i>"]

        sym = d.get("symbol", "")
        lines += [
            "━━━━━━━━━━━━━━━",
            f"{_tag(sym)} #{direction} #إشارة",
            "<i>هذه الإشارة لأغراض المتابعة فقط وليست توصية مالية.</i>",
        ]
        return "\n".join(lines)

    def _render_close(self, d: Dict[str, Any]) -> str:
        result = d.get("result", "—")
        emojis = {
            "win": "✅", "loss": "❌", "expired": "⌛", "breakeven": "⚪",
        }
        labels = {
            "win": "إغلاق بربح", "loss": "ضرب وقف الخسارة",
            "expired": "إغلاق بانتهاء المدة", "breakeven": "إغلاق متعادل",
        }
        emoji = emojis.get(result, "⚪")
        label = labels.get(result, "إغلاق")
        entry = d.get("entry_price")
        exit_p = d.get("exit_price")
        pnl = d.get("pnl_percent")
        sid = d.get("signal_id")
        is_quick = (d.get("kind") or "standard") == "quick"
        kemoji = "⚡" if is_quick else ""
        suffix = " (سريعة)" if is_quick else ""
        head = f"{emoji}{kemoji} <b>{label}{suffix} | {d.get('symbol')} {d.get('direction')}</b>"
        if sid is not None:
            head += f"  · #ID{sid}"

        lines = [
            head,
            "━━━━━━━━━━━━━━━",
            f"💵 سعر الدخول: <b>{_f(entry)}</b>",
            f"💰 سعر الخروج: <b>{_f(exit_p)}</b>",
            f"📈 النتيجة: <b>{_pf(pnl)}</b>",
            f"⏱️ المدة: {d.get('duration', '—')}",
        ]
        hits = []
        if d.get("tp1_hit"): hits.append("TP1")
        if d.get("tp2_hit"): hits.append("TP2")
        if d.get("tp3_hit"): hits.append("TP3")
        if hits:
            lines.append(f"🎯 الأهداف المحققة: {', '.join(hits)}")
        if d.get("notes"):
            lines.append(f"📝 {d['notes']}")
        sym = d.get("symbol", "")
        lines += [
            "━━━━━━━━━━━━━━━",
            f"{_tag(sym)} #نتيجة",
        ]
        return "\n".join(lines)

    def _compact_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ind = payload.get("indicators", {}).get(payload.get("primary_timeframe", "4h"), {})
        sr = payload.get("support_resistance", {})
        return {
            "symbol": payload.get("symbol"),
            "timestamp": payload.get("timestamp"),
            "timeframe": payload.get("primary_timeframe"),
            "ticker": payload.get("ticker"),
            "liquidity": payload.get("liquidity"),
            "market_structure": payload.get("market_structure"),
            "indicators": {
                k: ind.get(k) for k in [
                    "price", "rsi_14", "macd", "macd_signal", "ema_50", "ema_200",
                    "adx_14", "bb_upper", "bb_lower", "atr_14", "volume_ratio",
                ]
            },
            "support": sr.get("support", [])[:3],
            "resistance": sr.get("resistance", [])[:3],
        }
