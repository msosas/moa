"""Allocation primitives — reused by the waterfall's taxable-investing leaf."""

from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["low", "medium", "high"]


class ProviderSuggestion(BaseModel):
    name: str
    why: str
    url: str | None = Field(
        None,
        description="External link if applicable; null for generic suggestions like 'your main bank'.",
    )
    indicative_rate: float = Field(
        ..., description="Annual nominal rate (decimal). Approximate — confirm with the provider.",
    )


class AllocationSlice(BaseModel):
    """One row in a taxable-investing allocation. ``term_id`` matches a frontend glossary entry."""
    label: str
    term_id: str
    amount: float = Field(
        ..., description="Lump-sum portion to allocate today (may be 0 for slices fed only by contributions).",
    )
    monthly_contribution: float = Field(
        0, description="Recurring auto-invest amount flowing into this slice.",
    )
    contribution_starts_month: int = Field(
        0, description="0 = immediately; >0 = after a prior step finishes (e.g. EF fill).",
    )
    vehicle: str
    current_rate: float
    projected_value_at_horizon: float
    rationale: str
    suggested_providers: list[ProviderSuggestion] = Field(default_factory=list)
