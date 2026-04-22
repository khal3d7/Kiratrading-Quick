from __future__ import annotations

import time
from typing import Optional
import ccxt
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import settings
from utils import logger


# ccxt rate-limit-related exceptions we should back off on, not give up on.
_RETRYABLE = (
    ccxt.RateLimitExceeded,
    ccxt.DDoSProtection,
    ccxt.NetworkError,
    ccxt.RequestTimeout,
    ccxt.ExchangeNotAvailable,
)


class ExchangeClient:
    """Thin wrapper around a ccxt exchange with retry and safe defaults.

    Public market data does not require API keys. Keys are used only when
    provided to lift rate limits. The exchange id defaults to ``bybit``
    because Binance geo-blocks most cloud-provider IPs (Railway, AWS, GCP
    in some regions), which surfaces as ``ExchangeNotAvailable`` and
    prevents any data from being fetched.
    """

    def __init__(self, exchange_id: Optional[str] = None) -> None:
        exchange_id = (exchange_id or settings.exchange_id or "bybit").lower()

        params = {
            "enableRateLimit": True,
            # Slow ccxt's built-in throttle to be friendly to public endpoints
            # (ms between requests). Bybit defaults to ~50ms; 250ms = 4 req/s.
            "rateLimit": 250,
            "timeout": 30000,
            "options": {"defaultType": "spot"},
        }

        api_key, api_secret = self._resolve_keys(exchange_id)
        if api_key and api_secret:
            params["apiKey"] = api_key
            params["secret"] = api_secret

        try:
            self.exchange = getattr(ccxt, exchange_id)(params)
        except AttributeError:
            logger.warning(
                f"unknown exchange '{exchange_id}', falling back to bybit"
            )
            exchange_id = "bybit"
            self.exchange = ccxt.bybit(params)

        self.exchange_id = exchange_id
        logger.info(f"exchange client initialized: {exchange_id}")

    @staticmethod
    def _resolve_keys(exchange_id: str) -> tuple[str, str]:
        """Pick credentials. Generic EXCHANGE_API_* wins; Binance keys
        kept as a back-compat fallback when targeting binance."""
        if settings.exchange_api_key and settings.exchange_api_secret:
            return settings.exchange_api_key, settings.exchange_api_secret
        if exchange_id == "binance" and settings.binance_api_key and settings.binance_api_secret:
            return settings.binance_api_key, settings.binance_api_secret
        return "", ""

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200):
        return self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    def fetch_ticker(self, symbol: str):
        return self.exchange.fetch_ticker(symbol)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    def fetch_order_book(self, symbol: str, limit: int = 50):
        return self.exchange.fetch_order_book(symbol, limit=limit)

    def fetch_funding_rate(self, symbol: str) -> Optional[float]:
        """Best-effort funding rate from the configured exchange's perp market.
        Returns None when the exchange does not support it from this region."""
        try:
            futures_params = {
                "options": {"defaultType": "swap"},
                "enableRateLimit": True,
                "rateLimit": 250,
            }
            futures = getattr(ccxt, self.exchange_id)(futures_params)
            data = futures.fetch_funding_rate(symbol)
            return float(data.get("fundingRate") or 0.0)
        except Exception as e:
            logger.debug(f"funding rate unavailable for {symbol}: {e}")
            return None

    def cooldown(self, seconds: float = 0.0) -> None:
        """Manual sleep helper callers can use between bursts of requests."""
        if seconds > 0:
            time.sleep(seconds)
