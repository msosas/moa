from typing import Literal

from pydantic import BaseModel, Field

StrategyKey = Literal["fixed_1y", "fixed_2y", "fixed_3y", "fixed_5y", "floating"]


class LoanCompareRequest(BaseModel):
    principal: float = Field(..., gt=0, description="Loan amount (NZD)")
    term_years: int = Field(..., ge=5, le=40, description="Total loan term in years")
    strategies: list[StrategyKey] = Field(
        default_factory=lambda: ["fixed_1y", "fixed_3y", "fixed_5y", "floating"],
        description="Which strategies to compare",
    )


class LoanStrategyResult(BaseModel):
    strategy: StrategyKey
    label: str
    fixed_period_years: int
    initial_rate: float
    monthly_payment_during_fixed: float
    balance_after_fixed: float
    projected_total_interest: float
    projected_total_paid: float
    sensitivity_minus_1pct_total_interest: float
    sensitivity_plus_1pct_total_interest: float
    rationale: str


class LoanCompareResponse(BaseModel):
    principal: float
    term_years: int
    floating_rate_assumed_after_fixed: float
    results: list[LoanStrategyResult]
    best_strategy: StrategyKey
    summary: str
