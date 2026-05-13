"""Advisor endpoints — holistic plan, mortgage what-if, narrative model picker."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.logic.waterfall import build_plan
from app.models.profile import (
    AdvisorPlanResponse,
    Debt,
    FinancialProfile,
    MortgageOverride,
    WhatIfMortgageRequest,
)
from app.services.advisor_llm import AdvisorLLM, NarrativeProvider, get_advisor_llm
from app.services.rates import RateProvider, get_provider

router = APIRouter(prefix="/advisor", tags=["advisor"])


def _provider_dep() -> RateProvider:
    return get_provider()


def _advisor_llm_dep() -> AdvisorLLM:
    return get_advisor_llm()


ProviderQuery = Query(None, description="Narrative provider: ollama / templated")
ModelQuery = Query(None, description="Specific model id to use (provider-specific)")


@router.post("/plan", response_model=AdvisorPlanResponse)
async def plan_endpoint(
    profile: FinancialProfile,
    narrative_provider: NarrativeProvider | None = ProviderQuery,
    narrative_model: str | None = ModelQuery,
    provider: RateProvider = Depends(_provider_dep),
    llm: AdvisorLLM = Depends(_advisor_llm_dep),
) -> AdvisorPlanResponse:
    snapshot = await provider.get_market_snapshot()
    plan = build_plan(profile, snapshot)
    narrative = await llm.narrate(
        profile, plan, provider=narrative_provider, model=narrative_model,
    )
    return AdvisorPlanResponse(
        plan=plan,
        narrative=narrative.text,
        narrative_source=narrative.source,
        market_snapshot=snapshot,
    )


@router.post("/whatif/mortgage", response_model=AdvisorPlanResponse)
async def whatif_mortgage_endpoint(
    request: WhatIfMortgageRequest,
    narrative_provider: NarrativeProvider | None = ProviderQuery,
    narrative_model: str | None = ModelQuery,
    provider: RateProvider = Depends(_provider_dep),
    llm: AdvisorLLM = Depends(_advisor_llm_dep),
) -> AdvisorPlanResponse:
    profile = _apply_mortgage_override(request.profile, request.override)
    snapshot = await provider.get_market_snapshot()
    plan = build_plan(profile, snapshot)
    narrative = await llm.narrate(
        profile, plan, provider=narrative_provider, model=narrative_model,
    )
    return AdvisorPlanResponse(
        plan=plan,
        narrative=narrative.text,
        narrative_source=narrative.source,
        market_snapshot=snapshot,
    )


class ModelOption(BaseModel):
    id: str
    label: str
    provider: NarrativeProvider


class ModelListResponse(BaseModel):
    provider: NarrativeProvider
    available: bool
    models: list[ModelOption]


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    provider: Literal["ollama", "templated"] = Query(
        "ollama", description="Provider to list models for",
    ),
    llm: AdvisorLLM = Depends(_advisor_llm_dep),
) -> ModelListResponse:
    """List models available for a given narrative provider.

    For ``ollama`` this hits the configured Ollama instance's ``/api/tags``.
    For ``templated`` it returns the single deterministic option.
    """
    items = await llm.list_models(provider)
    return ModelListResponse(
        provider=provider,
        available=bool(items),
        models=[ModelOption(id=m.id, label=m.label, provider=m.provider) for m in items],
    )


def _apply_mortgage_override(profile: FinancialProfile, override: MortgageOverride) -> FinancialProfile:
    """Return a copy of ``profile`` with the mortgage adjusted per the override.

    No-op if the profile has no mortgage or the override contains nothing.
    """
    if profile.mortgage is None:
        return profile
    if override.principal is None and override.term_years is None:
        return profile

    update: dict = {}
    if override.principal is not None:
        update["balance"] = override.principal
    if override.term_years is not None:
        update["term_years_remaining"] = override.term_years
    new_mortgage = profile.mortgage.model_copy(update=update)

    # Re-mirror into debts: drop the old mortgage entry and add the new one so
    # the waterfall sees consistent state. (``model_validator`` only fires on
    # construction; ``model_copy`` skips it.)
    new_debts = [d for d in profile.debts if d.kind != "mortgage"]
    new_debts.append(Debt(
        kind="mortgage",
        label="Mortgage",
        balance=new_mortgage.balance,
        annual_rate=new_mortgage.annual_rate,
        min_monthly_payment=new_mortgage.monthly_payment or 0.0,
    ))
    return profile.model_copy(update={"mortgage": new_mortgage, "debts": new_debts})
