import httpx
import pytest
import respx

from app.config import get_settings
from app.services import rates as rates_service
from app.services.rates import (
    LiveProvider,
    MockProvider,
    _CachedProvider,
    get_provider,
    reset_provider,
)


def test_get_provider_default_is_mock(monkeypatch):
    monkeypatch.delenv("RATE_PROVIDER_TYPE", raising=False)
    get_settings.cache_clear()
    reset_provider()
    provider = get_provider()
    assert isinstance(provider, _CachedProvider)
    assert provider.name == "mock"


def test_get_provider_live_when_env_set(monkeypatch):
    monkeypatch.setenv("RATE_PROVIDER_TYPE", "live")
    monkeypatch.setenv("API_NINJAS_KEY", "fake-key")
    get_settings.cache_clear()
    reset_provider()
    provider = get_provider()
    assert provider.name == "live"


async def test_mock_provider_returns_deterministic_snapshot():
    snap1 = await MockProvider().get_market_snapshot()
    snap2 = await MockProvider().get_market_snapshot()
    assert snap1.mortgage == snap2.mortgage
    assert snap1.savings == snap2.savings
    assert snap1.source == "mock"


async def test_live_provider_falls_back_when_no_key():
    snap = await LiveProvider(api_key=None).get_market_snapshot()
    assert snap.source == "live-fallback"
    assert snap.mortgage.floating > 0  # mock data still populated


@respx.mock
async def test_live_provider_falls_back_on_http_error():
    respx.get("https://api.api-ninjas.com/v1/interestrate").mock(
        return_value=httpx.Response(500, json={"error": "boom"})
    )
    async with httpx.AsyncClient() as client:
        snap = await LiveProvider(api_key="fake-key", http_client=client).get_market_snapshot()
    assert snap.source == "live-fallback"


@respx.mock
async def test_live_provider_parses_nz_payload():
    respx.get("https://api.api-ninjas.com/v1/interestrate").mock(
        return_value=httpx.Response(200, json=[
            {"country": "United States", "central_bank_rate": 4.5},
            {"country": "New Zealand",  "central_bank_rate": 4.25},
        ])
    )
    async with httpx.AsyncClient() as client:
        snap = await LiveProvider(api_key="fake-key", http_client=client).get_market_snapshot()
    assert snap.source == "live"
    assert snap.central_bank_rate == pytest.approx(0.0425)
    # Mortgage rates derived with the documented spreads.
    assert snap.mortgage.floating == pytest.approx(0.0425 + 0.027)


async def test_cache_hit_avoids_repeat_fetch():
    """Second call within TTL must not invoke the inner provider again."""
    call_count = {"n": 0}

    class CountingProvider(MockProvider):
        async def get_market_snapshot(self):  # type: ignore[override]
            call_count["n"] += 1
            return await super().get_market_snapshot()

    cached = rates_service._CachedProvider(CountingProvider(), ttl_seconds=3600)
    await cached.get_market_snapshot()
    await cached.get_market_snapshot()
    await cached.get_market_snapshot()
    assert call_count["n"] == 1


async def test_cache_invalidate_forces_refetch():
    call_count = {"n": 0}

    class CountingProvider(MockProvider):
        async def get_market_snapshot(self):  # type: ignore[override]
            call_count["n"] += 1
            return await super().get_market_snapshot()

    cached = rates_service._CachedProvider(CountingProvider(), ttl_seconds=3600)
    await cached.get_market_snapshot()
    cached.invalidate()
    await cached.get_market_snapshot()
    assert call_count["n"] == 2
