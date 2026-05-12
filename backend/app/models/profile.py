"""Holistic FinancialProfile intake + RecommendedPlan output models.

These replace the disconnected SavingsPathRequest / LoanCompareRequest models.
The profile is the single intake; the plan is the structured output the
waterfall engine emits and the LLM narrative service explains.

Conventions:
- Rates are decimals (``0.0695`` for 6.95%).
- Amounts are NZD.
- ``Frequency`` lets the UI accept weekly/fortnightly inputs without forcing
  the user to do mental math.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from app.logic import nz_tax
from app.models.investment import ProviderSuggestion, RiskLevel
from app.models.loan import StrategyKey
from app.models.rates import MarketSnapshot

# --- Shared enums -----------------------------------------------------------

Frequency = Literal["weekly", "fortnightly", "monthly", "annual"]
JobStability = Literal["stable", "moderate", "unstable"]
DebtKind = Literal[
    "mortgage", "credit_card", "student_loan", "personal_loan", "car_loan", "bnpl", "other",
]
NarrationStyle = Literal["brief", "detailed"]


class Goal(StrEnum):
    BUILD_WEALTH = "build_wealth"
    BUY_FIRST_HOME = "buy_first_home"
    PAY_OFF_DEBT_FASTER = "pay_off_debt_faster"
    RETIRE_COMFORTABLY = "retire_comfortably"
    SAVE_FOR_KIDS = "save_for_kids"
    GENERAL_REVIEW = "general_review"


_FREQUENCY_TO_ANNUAL: dict[str, float] = {
    "weekly": 52.0,
    "fortnightly": 26.0,
    "monthly": 12.0,
    "annual": 1.0,
}


def to_annual(amount: float, frequency: Frequency) -> float:
    return amount * _FREQUENCY_TO_ANNUAL[frequency]


# --- Intake components ------------------------------------------------------

class IncomeSource(BaseModel):
    label: str = "Salary"
    gross_amount: float = Field(..., gt=0, description="Pre-tax amount at the chosen frequency")
    frequency: Frequency = "annual"
    is_primary: bool = True

    @computed_field
    @property
    def gross_annual(self) -> float:
        return to_annual(self.gross_amount, self.frequency)


class Expense(BaseModel):
    category: Literal[
        "housing", "utilities", "food", "transport", "childcare",
        "debt_servicing", "discretionary", "other",
    ] = "other"
    amount: float = Field(..., ge=0)
    frequency: Frequency = "monthly"

    @computed_field
    @property
    def monthly_amount(self) -> float:
        return to_annual(self.amount, self.frequency) / 12


class Debt(BaseModel):
    kind: DebtKind
    label: str | None = None
    balance: float = Field(..., ge=0)
    annual_rate: float = Field(..., ge=0, le=0.50, description="Decimal — 0.1995 for 19.95% APR")
    min_monthly_payment: float = Field(0, ge=0)


class Mortgage(BaseModel):
    """Specialised debt — the waterfall mirrors it into ``debts`` for iteration."""
    balance: float = Field(..., ge=0)
    annual_rate: float = Field(..., ge=0, le=0.30)
    term_years_remaining: int = Field(..., ge=1, le=40)
    current_strategy: StrategyKey | None = None
    fixed_until: date | None = None
    monthly_payment: float | None = Field(
        None, description="Actual monthly payment; derived from balance/rate/term if None",
    )
    property_value: float | None = Field(None, ge=0)


class KiwiSaver(BaseModel):
    balance: float = Field(0, ge=0)
    employee_rate: float = Field(nz_tax.KIWISAVER_DEFAULT_EMPLOYEE, ge=0.03, le=0.10)
    employer_rate: float = Field(nz_tax.KIWISAVER_DEFAULT_EMPLOYER, ge=0, le=0.10)
    fund_type: Literal["conservative", "balanced", "growth", "aggressive"] = "balanced"
    pir: float = Field(0.28, description="Prescribed Investor Rate — one of 0.105, 0.175, 0.28")

    @field_validator("employee_rate")
    @classmethod
    def _check_employee_rate(cls, v: float) -> float:
        if v not in nz_tax.KIWISAVER_EMPLOYEE_RATES:
            raise ValueError(f"employee_rate must be one of {nz_tax.KIWISAVER_EMPLOYEE_RATES}")
        return v

    @field_validator("pir")
    @classmethod
    def _check_pir(cls, v: float) -> float:
        if v not in nz_tax.PIE_TIERS:
            raise ValueError(f"pir must be one of {nz_tax.PIE_TIERS}")
        return v


class ExistingInvestment(BaseModel):
    label: str = "Investments"
    vehicle: Literal[
        "index_fund", "term_deposit", "savings", "shares", "property", "other",
    ] = "index_fund"
    balance: float = Field(..., ge=0)


# --- Main profile -----------------------------------------------------------

class FinancialProfile(BaseModel):
    """Single holistic intake. The waterfall consumes this to produce a plan."""

    # Personal
    age: int = Field(..., ge=16, le=100)
    dependents: int = Field(0, ge=0, le=10)
    job_stability: JobStability = "moderate"
    time_horizon_years: int = Field(10, ge=1, le=40)
    risk_tolerance: RiskLevel = "medium"

    # Cash flow
    incomes: list[IncomeSource] = Field(..., min_length=1)
    expenses: list[Expense] = Field(default_factory=list)

    # Debts (mortgage is also mirrored into debts for iteration)
    debts: list[Debt] = Field(default_factory=list)
    mortgage: Mortgage | None = None

    # Assets
    kiwisaver: KiwiSaver | None = None
    existing_investments: list[ExistingInvestment] = Field(default_factory=list)
    current_emergency_fund: float = Field(0, ge=0)
    lump_sum_available: float = Field(0, ge=0)

    # Intent
    goals: list[Goal] = Field(default_factory=lambda: [Goal.GENERAL_REVIEW])
    narration_style: NarrationStyle = "detailed"
    free_text_question: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _mirror_mortgage_into_debts(self) -> FinancialProfile:
        if self.mortgage is None:
            return self
        if not any(d.kind == "mortgage" for d in self.debts):
            self.debts = [
                *self.debts,
                Debt(
                    kind="mortgage",
                    label="Mortgage",
                    balance=self.mortgage.balance,
                    annual_rate=self.mortgage.annual_rate,
                    min_monthly_payment=self.mortgage.monthly_payment or 0.0,
                ),
            ]
        return self

    # --- Derived figures (computed_field so they ship in JSON to the LLM) ---

    @computed_field
    @property
    def gross_annual_income(self) -> float:
        return sum(inc.gross_annual for inc in self.incomes)

    @computed_field
    @property
    def net_monthly_income(self) -> float:
        return nz_tax.paye_net_monthly(self.gross_annual_income)

    @computed_field
    @property
    def total_monthly_expenses(self) -> float:
        return sum(e.monthly_amount for e in self.expenses)

    @computed_field
    @property
    def monthly_surplus(self) -> float:
        return max(0.0, self.net_monthly_income - self.total_monthly_expenses)

    @computed_field
    @property
    def savings_rate(self) -> float:
        if self.net_monthly_income <= 0:
            return 0.0
        return self.monthly_surplus / self.net_monthly_income

    @computed_field
    @property
    def total_debt_balance(self) -> float:
        return sum(d.balance for d in self.debts)

    @computed_field
    @property
    def high_interest_non_mortgage_debt(self) -> float:
        return sum(
            d.balance for d in self.debts
            if d.annual_rate > 0.08 and d.kind != "mortgage"
        )

    @computed_field
    @property
    def has_mortgage(self) -> bool:
        return self.mortgage is not None

    @computed_field
    @property
    def is_employed(self) -> bool:
        return any(inc.gross_annual > 0 for inc in self.incomes)


# --- Plan output models -----------------------------------------------------

class StepKind(StrEnum):
    STARTER_EMERGENCY_FUND = "starter_ef"
    HIGH_INTEREST_DEBT = "kill_high_interest_debt"
    KIWISAVER_EMPLOYER_MATCH = "kiwisaver_employer_match"
    FULL_EMERGENCY_FUND = "full_ef"
    MORTGAGE_VS_INVEST = "mortgage_vs_invest"
    KIWISAVER_BEYOND_MATCH = "kiwisaver_beyond_match"
    TAXABLE_INVESTING = "taxable_investing"
    NOTHING_LEFT = "nothing_left"


PriorityBand = Literal["must_do", "recommended", "optional"]
Confidence = Literal["high", "medium", "low"]


class RationaleBlock(BaseModel):
    """Structured rationale — numbers live in ``numeric_facts`` so the LLM can quote them verbatim."""
    primary_reason: str
    numeric_facts: dict[str, float] = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    priority: int = Field(..., ge=1)
    band: PriorityBand
    kind: StepKind
    action: str
    amount_today: float = Field(0, ge=0)
    monthly_amount: float = Field(0, ge=0)
    expected_outcome: dict[str, float] = Field(default_factory=dict)
    rationale: RationaleBlock
    confidence: Confidence = "high"
    references: list[str] = Field(default_factory=list)
    suggested_providers: list[ProviderSuggestion] = Field(default_factory=list)


class CashFlowSummary(BaseModel):
    gross_annual_income: float
    net_monthly_income: float
    total_monthly_expenses: float
    monthly_surplus: float
    savings_rate: float


class HorizonProjection(BaseModel):
    emergency_fund: float
    kiwisaver: float
    taxable_investments: float
    debt_remaining: float
    total_net_worth: float


class RecommendedPlan(BaseModel):
    steps: list[PlanStep]
    cash_flow: CashFlowSummary
    unallocated_lump_sum: float = Field(0, ge=0)
    unallocated_monthly: float = Field(0, ge=0)
    horizon_projection: HorizonProjection
    market_snapshot: MarketSnapshot


# --- Wire models ------------------------------------------------------------

NarrativeSource = Literal["llm", "fallback"]


class AdvisorPlanResponse(BaseModel):
    plan: RecommendedPlan
    narrative: str
    narrative_source: NarrativeSource
    market_snapshot: MarketSnapshot


class MortgageOverride(BaseModel):
    """Inputs the user can tweak in the What-if Mortgage panel."""
    principal: float | None = Field(None, gt=0)
    term_years: int | None = Field(None, ge=5, le=40)
    strategies: list[StrategyKey] | None = None


class WhatIfMortgageRequest(BaseModel):
    profile: FinancialProfile
    override: MortgageOverride = Field(default_factory=MortgageOverride)
