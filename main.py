"""Crypto Trading Intelligence System — entry point.

Runs:
- Telegram bot (interactive control panel)
- Channel publisher (analyses + trade notifications)
- Scheduler (analysis + strategy scan + trade monitoring + reports)
"""
from __future__ import annotations

import asyncio
import signal

from dotenv import load_dotenv

load_dotenv()

from config import settings  # noqa: E402
from utils import setup_logging, logger  # noqa: E402
from database import init_db  # noqa: E402
from telegram_bot import TradingBot  # noqa: E402
from scheduler import JobOrchestrator  # noqa: E402


async def main_async() -> None:
    setup_logging()
    logger.info("=" * 60)
    logger.info("Crypto Trading Intelligence System — starting")
    logger.info("=" * 60)

    init_db()
    logger.info("database ready")

    orchestrator = JobOrchestrator()
    orchestrator.start()

    if not settings.has_telegram:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot disabled, scheduler still running")
        # stay alive forever
        stop = asyncio.Event()
        await stop.wait()
        return

    bot = TradingBot()
    app = bot.build()

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("telegram bot is polling")

    try:
        stop = asyncio.Event()

        def _on_signal(*_):
            logger.info("shutdown signal received")
            stop.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _on_signal)
            except NotImplementedError:
                pass

        await stop.wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        orchestrator.scheduler.shutdown(wait=False)
        logger.info("shutdown complete")


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
