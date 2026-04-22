from __future__ import annotations

import re
from typing import Optional
from telegram import Bot
from telegram.constants import ParseMode

from config import settings
from utils import logger


def _to_html(text: str) -> str:
    """Convert common Markdown (**, *, __, _) into safe Telegram HTML.
    Arabic text + LLM output often has unbalanced asterisks that break the
    legacy Markdown parser; HTML is far more forgiving."""
    # Escape HTML special chars first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold: **x** or __x__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text, flags=re.DOTALL)
    # Italic / single-asterisk bold (common in legacy Markdown): *x*
    # Use a guarded pattern to avoid matching standalone *
    text = re.sub(r"(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"<b>\1</b>", text)
    # Strip any remaining stray asterisks/underscores
    text = text.replace("*", "").replace("`", "")
    return text


class ChannelPublisher:
    """Publishes formatted messages to the analysis and trades channels."""

    def __init__(self, bot: Optional[Bot] = None) -> None:
        if bot is None and settings.telegram_bot_token:
            bot = Bot(token=settings.telegram_bot_token)
        self.bot = bot

    async def publish_analysis(self, text: str) -> None:
        await self._send(settings.daily_channel, text)

    async def publish_trade(self, text: str) -> None:
        await self._send(settings.trades_channel, text)

    async def _send(self, chat_id: str, text: str) -> None:
        if not self.bot or not chat_id:
            logger.warning("telegram channel not configured — message dropped")
            return
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=_to_html(text),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"failed to send to {chat_id}: {e}")
            # retry without markdown if formatting fails
            try:
                await self.bot.send_message(chat_id=chat_id, text=text, disable_web_page_preview=True)
            except Exception as e2:
                logger.error(f"plain send also failed: {e2}")
