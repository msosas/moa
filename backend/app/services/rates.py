"""External market rates service.

Architecture: Provider Pattern. The application talks to the abstract
``RateProvider`` interface; ``MockProvider`` and ``LiveProvider`` are the two
concrete implementations. The active one is chosen by the
``RATE_PROVIDER_TYPE`` environment variable (``mock`` or ``live``).

The ``LiveProvider`` calls API Ninjas and *always* falls back to mock data on
any error (missing key, network failure, schema change). This keeps the demo
working when APIs are flaky and lets the frontend always render something
sensible.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import ClassVar

import httpx

from app.config import Settings, get_settings
from app.models.rates import MarketSnapshot, MortgageRates, SavingsRates

logger = logging.getLogger(__name__)


# --- Mock data: deterministic 2026 NZ-flavored rates --------------------------
# Calibrated to early-2026 NZ conditions: OCR around 3.25%, big-bank 12-month
# TDs in the 3.7–3.9% band (e.g. BNZ ~3.8%), specialist banks slightly higher,
# mortgage rates roughly OCR + 200bps for short fixed terms.
_MOCK_MORTGAGE = MortgageRates(
    fixed_1y=0.0535,
    fixed_2y=0.0510,
    fixed_3y=0.0500,
    fixed_5y=0.0525,
    floating=0.0695,
)
_MOCK_SAVINGS = SavingsRates(
    high_yield_savings=0.0320,
    term_deposit_6m=0.0385,
    term_deposit_12m=0.0400,
    term_deposit_24m=0.0395,
)
_MOCK_INDEX_FUND_RETURN = 0.0750  # Long-run global average — not tied to OCR.
_MOCK_INFLATION = 0.0220
_MOCK_OCR = 0.0325


def _mock_snapshot(source: str = "mock") -> MarketSnapshot:
    return MarketSnapshot(
        mortgage=_MOCK_MORTGAGE,
        savings=_MOCK_SAVINGS,
        index_fund_avg_return=_MOCK_INDEX_FUND_RETURN,
        inflation=_MOCK_INFLATION,
        central_bank_rate=_MOCK_OCR,
        source=source,  # type: ignore[arg-type]
        fetched_at=datetime.now(timezone.utc),
    )


# --- Provider interface -------------------------------------------------------
class RateProvider(ABC):
    name: ClassVar[str] = "abstract"

    @abstractmethod
    async def get_market_snapshot(self) -> MarketSnapshot:
        ...

    async def get_mortgage_rates(self) -> MortgageRates:
        snap = await self.get_market_snapshot()
        return snap.mortgage

    async def get_savings_rates(self) -> SavingsRates:
        snap = await self.get_market_snapshot()
        return snap.savings


class MockProvider(RateProvider):
    name: ClassVar[str] = "mock"

    async def get_market_snapshot(self) -> MarketSnapshot:
        return _mock_snapshot(source="mock")


class LiveProvider(RateProvider):
    """Live provider backed by API Ninjas.

    Falls back to mock data on any failure so the UI never breaks. The
    ``source`` field on the response is set to ``live-fallback`` in that case
    so callers can surface a "data may be stale" hint if they wish.
    """

    name: ClassVar[str] = "live"
    BASE_URL: ClassVar[str] = "https://api.api-ninjas.com/v1"

    def __init__(self, api_key: str | None, http_client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = http_client

    async def _client_or_default(self) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        return httpx.AsyncClient(timeout=httpx.Timeout(5.0))

    async def get_market_snapshot(self) -> MarketSnapshot:
        if not self._api_key:
            logger.warning("LiveProvider: API_NINJAS_KEY not set; serving mock data")
            return _mock_snapshot(source="live-fallback")

        client = await self._client_or_default()
        owns_client = self._client is None
        try:
            resp = await client.get(
                f"{self.BASE_URL}/interestrate",
                headers={"X-Api-Key": self._api_key},
            )
            resp.raise_for_status()
            payload = resp.json()
            ocr = _extract_ocr(payload)
            return MarketSnapshot(
                mortgage=_mortgage_from_ocr(ocr),
                savings=_savings_from_ocr(ocr),
                index_fund_avg_return=_MOCK_INDEX_FUND_RETURN,
                inflation=_MOCK_INFLATION,
                central_bank_rate=ocr,
                source="live",
                fetched_at=datetime.now(timezone.utc),
            )
        except Exception as exc:  # noqa: BLE001 — broad on purpose; demo must not crash
            logger.warning("LiveProvider failed (%s); falling back to mock", exc)
            return _mock_snapshot(source="live-fallback")
        finally:
            if owns_client:
                await client.aclose()


def _extract_ocr(payload: object) -> float:
    """Pull a usable cash-rate number out of the API Ninjas /interestrate payload.

    The exact schema varies; we accept either a list of country entries with
    ``central_bank_rate`` or a single object with ``non_seasonally_adjusted``.
    Any miss raises and the caller falls back to mock.
    """
    if isinstance(payload, list) and payload:
        for entry in payload:
            if isinstance(entry, dict) and entry.get("country", "").lower() in {"new zealand", "nz"}:
                return float(entry["central_bank_rate"]) / 100
        first = payload[0]
        if isinstance(first, dict) and "central_bank_rate" in first:
            return float(first["central_bank_rate"]) / 100
    if isinstance(payload, dict):
        if "central_bank_rate" in payload:
            return float(payload["central_bank_rate"]) / 100
        if "non_seasonally_adjusted" in payload:
            return float(payload["non_seasonally_adjusted"]) / 100
    raise ValueError(f"unrecognised interestrate payload shape: {type(payload).__name__}")


def _mortgage_from_ocr(ocr: float) -> MortgageRates:
    """Approximate retail mortgage rates from the cash rate using typical spreads."""
    return MortgageRates(
        fixed_1y=ocr + 0.020,
        fixed_2y=ocr + 0.018,
        fixed_3y=ocr + 0.017,
        fixed_5y=ocr + 0.019,
        floating=ocr + 0.027,
    )


def _savings_from_ocr(ocr: float) -> SavingsRates:
    return SavingsRates(
        high_yield_savings=max(0.0, ocr - 0.001),
        term_deposit_6m=max(0.0, ocr + 0.005),
        term_deposit_12m=max(0.0, ocr + 0.008),
        term_deposit_24m=max(0.0, ocr + 0.006),
    )


# --- TTL cache + factory ------------------------------------------------------
class _CachedProvider(RateProvider):
    """Wraps any provider with an in-memory TTL cache."""

    def __init__(self, inner: RateProvider, ttl_seconds: int) -> None:
        self._inner = inner
        self._ttl = ttl_seconds
        self._cache: tuple[float, MarketSnapshot] | None = None

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._inner.name

    async def get_market_snapshot(self) -> MarketSnapshot:
        now = time.monotonic()
        if self._cache is not None:
            ts, snap = self._cache
            if now - ts < self._ttl:
                return snap
        snap = await self._inner.get_market_snapshot()
        self._cache = (now, snap)
        return snap

    def invalidate(self) -> None:
        self._cache = None


_provider_singleton: _CachedProvider | None = None


def _build_provider(settings: Settings) -> RateProvider:
    if settings.rate_provider_type == "live":
        return LiveProvider(api_key=settings.api_ninjas_key)
    return MockProvider()


def get_provider(settings: Settings | None = None) -> RateProvider:
    """Return the configured provider, wrapped in a TTL cache.

    Process-wide singleton — first call decides which provider to build.
    Tests should call :func:`reset_provider` between cases.
    """
    global _provider_singleton
    if _provider_singleton is None:
        s = settings or get_settings()
        _provider_singleton = _CachedProvider(_build_provider(s), ttl_seconds=s.rates_cache_ttl_seconds)
    return _provider_singleton


def reset_provider() -> None:
    global _provider_singleton
    _provider_singleton = None
