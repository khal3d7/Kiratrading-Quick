from __future__ import annotations

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Exchange (ccxt id: kucoin | okx | gateio | mexc | bybit | binance ...)
    # Default is kucoin because Binance and Bybit both geo-block most
    # cloud-provider IPs (including Railway's us-west2), causing 403/451.
    # KuCoin and OKX serve public market data from cloud regions reliably.
    exchange_id: str = "kucoin"
    binance_api_key: str = ""
    binance_api_secret: str = ""
    exchange_api_key: str = ""
    exchange_api_secret: str = ""

    # Telegram
    telegram_bot_token: str = ""
    daily_analysis_channel_id: str = ""
    trades_channel_id: str = ""
    admin_user_ids: str = ""

    # AI
    ai_provider: str = "gemini"  # gemini | openai | anthropic
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Database
    database_url: str = "sqlite:///trading.db"

    # Trading
    initial_capital: float = 10000.0
    max_risk_per_trade: float = 0.02
    max_open_trades: int = 5
    min_risk_reward: float = 2.0

    # Optional
    coingecko_api_key: str = ""
    log_level: str = "INFO"
    timezone: str = "Asia/Riyadh"

    @property
    def admin_ids(self) -> List[int]:
        if not self.admin_user_ids:
            return []
        ids: List[int] = []
        for raw in self.admin_user_ids.split(","):
            raw = raw.strip()
            if raw:
                try:
                    ids.append(int(raw))
                except ValueError:
                    pass
        return ids

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token)

    @staticmethod
    def _normalize_channel(raw: str) -> str:
        """Telegram channel IDs in API calls must be prefixed with -100.
        Accept either the raw numeric ID or the already-prefixed form."""
        raw = (raw or "").strip()
        if not raw:
            return raw
        if raw.startswith("-100"):
            return raw
        if raw.startswith("@"):
            return raw  # username is also valid
        # numeric without prefix → add -100
        digits = raw.lstrip("-")
        if digits.isdigit():
            return f"-100{digits}"
        return raw

    @property
    def daily_channel(self) -> str:
        return self._normalize_channel(self.daily_analysis_channel_id)

    @property
    def trades_channel(self) -> str:
        return self._normalize_channel(self.trades_channel_id)

    @property
    def has_ai(self) -> bool:
        if self.ai_provider == "openai":
            return bool(self.openai_api_key)
        if self.ai_provider == "anthropic":
            return bool(self.anthropic_api_key)
        if self.ai_provider == "gemini":
            return bool(self.gemini_api_key)
        return False


settings = Settings()
