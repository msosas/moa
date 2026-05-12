"""Integration tests for the advisor router.

Uses FastAPI's TestClient with a stubbed AdvisorLLM (overridden via dependency
injection) so no real Anthropic call is made.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.advisor import _advisor_llm_dep
from app.services.advisor_llm import NarrativeResult


class _StubLLM:
    async def narrate(self, profile, plan, *, provider=None, model=None):  # noqa: ANN001 — duck-typed
        return NarrativeResult(
            text="stubbed narrative",
            source="llm",
            provider=provider or "anthropic",
            model=model or "stub",
            cache_read_tokens=None,
        )

    async def list_models(self, provider):  # noqa: ANN001
        return []


@pytest.fixture
def client():
    app.dependency_overrides[_advisor_llm_dep] = _StubLLM
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _minimal_profile() -> dict:
    return {
        "age": 35,
        "incomes": [{"gross_amount": 80_000, "frequency": "annual"}],
        "expenses": [{"amount": 3_500, "frequency": "monthly"}],
    }


def test_plan_endpoint_returns_valid_response(client):
    resp = client.post("/api/advisor/plan", json=_minimal_profile())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["narrative"] == "stubbed narrative"
    assert body["narrative_source"] == "llm"
    assert isinstance(body["plan"]["steps"], list)
    assert len(body["plan"]["steps"]) >= 1
    assert body["market_snapshot"]["source"] in ("mock", "live-fallback")


def test_plan_endpoint_validates_profile(client):
    resp = client.post("/api/advisor/plan", json={"age": 5, "incomes": []})
    assert resp.status_code == 422


def test_old_endpoints_are_removed(client):
    """Sanity check that the legacy /investment and /loan routes are gone."""
    assert client.post("/api/investment/savings-path", json={}).status_code == 404
    assert client.post("/api/loan/compare", json={}).status_code == 404


def test_whatif_mortgage_only_touches_mortgage_step(client):
    profile = {
        **_minimal_profile(),
        "current_emergency_fund": 50_000,
        "mortgage": {
            "balance": 500_000, "annual_rate": 0.0535, "term_years_remaining": 25,
        },
    }
    base = client.post("/api/advisor/plan", json=profile).json()
    altered = client.post(
        "/api/advisor/whatif/mortgage",
        json={"profile": profile, "override": {"principal": 700_000}},
    ).json()

    base_steps = {s["kind"]: s for s in base["plan"]["steps"]}
    altered_steps = {s["kind"]: s for s in altered["plan"]["steps"]}
    assert "mortgage_vs_invest" in base_steps
    assert "mortgage_vs_invest" in altered_steps

    # Mortgage step's projected interest must differ when principal changes.
    base_m = base_steps["mortgage_vs_invest"]
    altered_m = altered_steps["mortgage_vs_invest"]
    assert (
        base_m["expected_outcome"]["best_strategy_total_interest"]
        != altered_m["expected_outcome"]["best_strategy_total_interest"]
    )

    # Non-mortgage steps should be untouched. Only the mortgage step matters here,
    # but any common step (e.g. taxable_investing) must have identical expected
    # outcomes since the rest of the cashflow picture is the same.
    for kind, step in altered_steps.items():
        if kind == "mortgage_vs_invest":
            continue
        if kind in base_steps:
            assert step["expected_outcome"] == base_steps[kind]["expected_outcome"]


def test_models_endpoint_returns_provider_list(client):
    resp = client.get("/api/advisor/models?provider=templated")
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "templated"
    assert body["available"] is False or len(body["models"]) >= 1


def test_whatif_with_no_override_returns_same_plan(client):
    profile = {
        **_minimal_profile(),
        "current_emergency_fund": 50_000,
        "mortgage": {
            "balance": 500_000, "annual_rate": 0.0535, "term_years_remaining": 25,
        },
    }
    base = client.post("/api/advisor/plan", json=profile).json()
    altered = client.post(
        "/api/advisor/whatif/mortgage", json={"profile": profile},
    ).json()
    base_kinds = [s["kind"] for s in base["plan"]["steps"]]
    altered_kinds = [s["kind"] for s in altered["plan"]["steps"]]
    assert base_kinds == altered_kinds
