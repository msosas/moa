"""Tests for the AdvisorLLM narrative service.

All cases run offline by injecting an ``httpx.MockTransport`` into either the
Anthropic SDK's underlying client or a directly-passed Ollama client. The
demo-never-breaks contract is exercised via the 5xx, timeout, and missing-key
paths for both providers.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import anthropic
import httpx

from app.logic.waterfall import build_plan
from app.models.profile import (
    Expense,
    FinancialProfile,
    IncomeSource,
)
from app.models.rates import MarketSnapshot, MortgageRates, SavingsRates
from app.services.advisor_llm import AdvisorLLM


# --- Fixtures ---------------------------------------------------------------

def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        mortgage=MortgageRates(
            fixed_1y=0.0535, fixed_2y=0.0510, fixed_3y=0.05,
            fixed_5y=0.0525, floating=0.0695,
        ),
        savings=SavingsRates(
            high_yield_savings=0.0320,
            term_deposit_6m=0.0385,
            term_deposit_12m=0.0400,
            term_deposit_24m=0.0395,
        ),
        index_fund_avg_return=0.075,
        inflation=0.022,
        central_bank_rate=0.0325,
        source="mock",
        fetched_at=datetime.now(timezone.utc),
    )


def _profile() -> FinancialProfile:
    return FinancialProfile(
        age=35,
        dependents=0,
        job_stability="moderate",
        time_horizon_years=10,
        risk_tolerance="medium",
        incomes=[IncomeSource(gross_amount=80_000)],
        expenses=[Expense(amount=3_500, frequency="monthly")],
        lump_sum_available=10_000,
    )


def _anthropic_success_body(text: str = "Here's what I'd suggest…") -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": "claude-sonnet-4-6",
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 500,
            "output_tokens": 200,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 480,
        },
    }


def _build_anthropic_client(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport, base_url="https://api.anthropic.com")
    return anthropic.AsyncAnthropic(api_key="test-key", http_client=http_client)


def _build_ollama_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- Disabled / no-provider paths ------------------------------------------

async def test_disabled_short_circuits_no_http_call():
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    llm = AdvisorLLM(anthropic_api_key="anything", enabled=False)
    result = await llm.narrate(profile, plan)
    assert result.source == "fallback"
    assert result.text


async def test_no_provider_returns_fallback():
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    llm = AdvisorLLM(anthropic_api_key=None, ollama_base_url=None, enabled=True)
    result = await llm.narrate(profile, plan)
    assert result.source == "fallback"


async def test_explicit_templated_request_skips_llm():
    """Passing provider='templated' bypasses both backends and returns the fallback."""
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    llm = AdvisorLLM(anthropic_api_key="test-key", enabled=True)
    result = await llm.narrate(profile, plan, provider="templated")
    assert result.source == "fallback"


# --- Anthropic success path -------------------------------------------------

async def test_anthropic_success_returns_llm_text_with_cache_metadata():
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_anthropic_success_body("Walk through your plan step by step."))

    client = _build_anthropic_client(handler)
    llm = AdvisorLLM(anthropic_api_key="test-key", anthropic_client=client)
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    result = await llm.narrate(profile, plan)

    assert result.source == "llm"
    assert result.provider == "anthropic"
    assert result.text == "Walk through your plan step by step."
    assert result.cache_read_tokens == 480
    assert result.model == "claude-sonnet-4-6"


async def test_anthropic_system_blocks_carry_cache_control():
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_anthropic_success_body())

    client = _build_anthropic_client(handler)
    llm = AdvisorLLM(anthropic_api_key="test-key", anthropic_client=client)
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    await llm.narrate(profile, plan)

    assert len(captured) == 1
    system_blocks = captured[0]["system"]
    assert len(system_blocks) == 4
    for block in system_blocks:
        assert block["type"] == "text"
        assert block["cache_control"] == {"type": "ephemeral"}


async def test_anthropic_model_override_per_request():
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_anthropic_success_body())

    client = _build_anthropic_client(handler)
    llm = AdvisorLLM(anthropic_api_key="test-key", anthropic_client=client)
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    await llm.narrate(profile, plan, provider="anthropic", model="claude-haiku-4-5")
    assert captured[0]["model"] == "claude-haiku-4-5"


# --- Anthropic failure paths ------------------------------------------------

async def test_anthropic_5xx_falls_back():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"type": "server_error", "message": "boom"}})

    client = _build_anthropic_client(handler)
    llm = AdvisorLLM(anthropic_api_key="test-key", anthropic_client=client)
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    result = await llm.narrate(profile, plan)
    assert result.source == "fallback"


async def test_anthropic_network_error_falls_back():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = _build_anthropic_client(handler)
    llm = AdvisorLLM(anthropic_api_key="test-key", anthropic_client=client)
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    result = await llm.narrate(profile, plan)
    assert result.source == "fallback"


# --- Ollama success path ---------------------------------------------------

async def test_ollama_narrate_success_uses_local_model():
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        captured.append(body)
        return httpx.Response(200, json={
            "model": body["model"],
            "message": {"role": "assistant", "content": "Local model says hi."},
            "done": True,
        })

    client = _build_ollama_client(handler)
    llm = AdvisorLLM(ollama_base_url="http://ollama.test", ollama_client=client)
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    result = await llm.narrate(profile, plan, provider="ollama", model="llama3.2:3b")
    assert result.source == "llm"
    assert result.provider == "ollama"
    assert result.model == "llama3.2:3b"
    assert result.text == "Local model says hi."
    assert captured[0]["model"] == "llama3.2:3b"
    # Combined system + user messages — Ollama doesn't support multi-block systems.
    roles = [m["role"] for m in captured[0]["messages"]]
    assert roles == ["system", "user"]


async def test_ollama_auto_picks_first_model_when_none_specified():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={
                "models": [
                    {"name": "llama3.2:3b"},
                    {"name": "qwen2.5:7b"},
                ],
            })
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={
                "message": {"role": "assistant", "content": "ok"}, "done": True,
            })
        return httpx.Response(404)

    client = _build_ollama_client(handler)
    llm = AdvisorLLM(ollama_base_url="http://ollama.test", ollama_client=client)
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    result = await llm.narrate(profile, plan, provider="ollama")
    assert result.source == "llm"
    assert result.model == "llama3.2:3b"


async def test_ollama_5xx_falls_back():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _build_ollama_client(handler)
    llm = AdvisorLLM(ollama_base_url="http://ollama.test", ollama_client=client)
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    result = await llm.narrate(profile, plan, provider="ollama", model="anything")
    assert result.source == "fallback"


async def test_ollama_with_no_models_falls_back():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": []})
        return httpx.Response(404)

    client = _build_ollama_client(handler)
    llm = AdvisorLLM(ollama_base_url="http://ollama.test", ollama_client=client)
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    result = await llm.narrate(profile, plan, provider="ollama")
    assert result.source == "fallback"


# --- list_models -----------------------------------------------------------

async def test_list_models_anthropic_returns_curated_presets():
    llm = AdvisorLLM(anthropic_api_key="test-key")
    models = await llm.list_models("anthropic")
    assert any(m.id.startswith("claude-") for m in models)
    assert all(m.provider == "anthropic" for m in models)


async def test_list_models_anthropic_empty_without_key():
    llm = AdvisorLLM(anthropic_api_key=None)
    assert await llm.list_models("anthropic") == []


async def test_list_models_ollama_proxies_tags_endpoint():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={
            "models": [
                {"name": "llama3.2:latest"},
                {"name": "qwen2.5:7b"},
            ],
        })

    client = _build_ollama_client(handler)
    llm = AdvisorLLM(ollama_base_url="http://ollama.test", ollama_client=client)
    models = await llm.list_models("ollama")
    ids = [m.id for m in models]
    assert ids == ["llama3.2:latest", "qwen2.5:7b"]
    assert models[0].label == "llama3.2"          # ":latest" stripped
    assert models[1].label == "qwen2.5 (7b)"
    assert all(m.provider == "ollama" for m in models)


async def test_list_models_ollama_empty_when_unreachable():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = _build_ollama_client(handler)
    llm = AdvisorLLM(ollama_base_url="http://ollama.test", ollama_client=client)
    assert await llm.list_models("ollama") == []


# --- Fallback content ------------------------------------------------------

async def test_fallback_narrative_references_all_steps():
    profile = _profile()
    plan = build_plan(profile, _snapshot())
    llm = AdvisorLLM(anthropic_api_key=None, ollama_base_url=None, enabled=False)
    result = await llm.narrate(profile, plan)
    for step in plan.steps:
        assert step.action in result.text


async def test_brief_narration_style_passed_through_to_anthropic():
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_anthropic_success_body())

    client = _build_anthropic_client(handler)
    llm = AdvisorLLM(anthropic_api_key="test-key", anthropic_client=client)
    profile = _profile().model_copy(update={"narration_style": "brief"})
    plan = build_plan(profile, _snapshot())
    await llm.narrate(profile, plan)
    assert "brief voice" in captured[0]["messages"][0]["content"]
