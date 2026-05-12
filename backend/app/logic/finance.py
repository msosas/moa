"""Pure financial math — no I/O, no globals.

All rates are decimals (``0.065`` = 6.5%); all amounts are NZD.

This module is intentionally the *primitive* layer: amortization, compound
growth, fix-vs-float strategy comparison, and a leaf taxable-investing
allocator. The holistic prioritization (emergency-fund sizing, debt vs invest,
KiwiSaver, mortgage strategy in context) lives one layer up in
``app.logic.waterfall``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.data.providers import HIGH_YIELD_SAVINGS, INDEX_FUND, TERM_DEPOSIT_12M, materialise
from app.models.investment import AllocationSlice, ProviderSuggestion, RiskLevel
from app.models.loan import LoanCompareRequest, LoanCompareResponse, LoanStrategyResult, StrategyKey
from app.models.rates import MarketSnapshot

# --- Loan / mortgage math -----------------------------------------------------

def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    """Standard amortizing loan payment. Returns 0 if principal is 0."""
    if principal <= 0:
        return 0.0
    months = years * 12
    if annual_rate == 0:
        return principal / months
    r = annual_rate / 12
    factor = (1 + r) ** months
    return principal * r * factor / (factor - 1)


def remaining_balance(principal: float, annual_rate: float, years: int, months_elapsed: int) -> float:
    """Outstanding balance after ``months_elapsed`` of an amortizing loan."""
    if months_elapsed <= 0:
        return principal
    months = years * 12
    if months_elapsed >= months:
        return 0.0
    if annual_rate == 0:
        return principal * (1 - months_elapsed / months)
    r = annual_rate / 12
    factor_total = (1 + r) ** months
    factor_elapsed = (1 + r) ** months_elapsed
    return principal * (factor_total - factor_elapsed) / (factor_total - 1)


@dataclass
class _StrategyConfig:
    key: StrategyKey
    label: str
    fixed_period_years: int
    rate_attr: str


_STRATEGY_CONFIGS: dict[StrategyKey, _StrategyConfig] = {
    "fixed_1y":  _StrategyConfig("fixed_1y",  "1-year fixed",  1, "fixed_1y"),
    "fixed_2y":  _StrategyConfig("fixed_2y",  "2-year fixed",  2, "fixed_2y"),
    "fixed_3y":  _StrategyConfig("fixed_3y",  "3-year fixed",  3, "fixed_3y"),
    "fixed_5y":  _StrategyConfig("fixed_5y",  "5-year fixed",  5, "fixed_5y"),
    "floating":  _StrategyConfig("floating",  "Floating",      0, "floating"),
}


def _project_total_interest(principal: float, fixed_rate: float, fixed_period_years: int,
                            term_years: int, post_fixed_rate: float) -> tuple[float, float, float]:
    """Compute (monthly_payment_during_fixed, balance_after_fixed, total_interest_over_term).

    Re-amortizes at ``post_fixed_rate`` for the remainder once the fixed window
    ends. For floating-only (fixed_period=0), the loan is amortized at
    ``post_fixed_rate`` throughout.
    """
    if fixed_period_years <= 0:
        pay = monthly_payment(principal, post_fixed_rate, term_years)
        total_paid = pay * term_years * 12
        return pay, principal, total_paid - principal

    fixed_months = fixed_period_years * 12
    pay_fixed = monthly_payment(principal, fixed_rate, term_years)
    interest_during_fixed = pay_fixed * fixed_months - (
        principal - remaining_balance(principal, fixed_rate, term_years, fixed_months)
    )
    balance_after = remaining_balance(principal, fixed_rate, term_years, fixed_months)

    remaining_years = term_years - fixed_period_years
    if remaining_years <= 0:
        return pay_fixed, balance_after, interest_during_fixed

    pay_after = monthly_payment(balance_after, post_fixed_rate, remaining_years)
    interest_after = pay_after * remaining_years * 12 - balance_after
    return pay_fixed, balance_after, interest_during_fixed + interest_after


def compare_loan_strategies(req: LoanCompareRequest, snapshot: MarketSnapshot) -> LoanCompareResponse:
    floating = snapshot.mortgage.floating
    results: list[LoanStrategyResult] = []

    for key in req.strategies:
        cfg = _STRATEGY_CONFIGS[key]
        rate = getattr(snapshot.mortgage, cfg.rate_attr)
        pay, balance_after, total_interest = _project_total_interest(
            req.principal, rate, cfg.fixed_period_years, req.term_years, floating,
        )
        _, _, total_minus = _project_total_interest(
            req.principal, rate, cfg.fixed_period_years, req.term_years, max(0.0, floating - 0.01),
        )
        _, _, total_plus = _project_total_interest(
            req.principal, rate, cfg.fixed_period_years, req.term_years, floating + 0.01,
        )
        rationale = _loan_rationale(cfg, rate, floating, total_minus, total_plus, total_interest)
        results.append(LoanStrategyResult(
            strategy=cfg.key,
            label=cfg.label,
            fixed_period_years=cfg.fixed_period_years,
            initial_rate=rate,
            monthly_payment_during_fixed=round(pay, 2),
            balance_after_fixed=round(balance_after, 2),
            projected_total_interest=round(total_interest, 2),
            projected_total_paid=round(req.principal + total_interest, 2),
            sensitivity_minus_1pct_total_interest=round(total_minus, 2),
            sensitivity_plus_1pct_total_interest=round(total_plus, 2),
            rationale=rationale,
        ))

    best = min(results, key=lambda r: r.projected_total_interest)
    summary = (
        f"Assuming the floating rate stays at {floating * 100:.2f}% after any fixed period ends, "
        f"the strategy with the lowest projected total interest is '{best.label}' "
        f"at ${best.projected_total_interest:,.0f}. "
        "The sensitivity columns show how that figure shifts if the floating rate ends up "
        "1% lower or higher — that is the opportunity cost of locking in for longer or shorter."
    )
    return LoanCompareResponse(
        principal=req.principal,
        term_years=req.term_years,
        floating_rate_assumed_after_fixed=floating,
        results=results,
        best_strategy=best.strategy,
        summary=summary,
    )


def _loan_rationale(cfg: _StrategyConfig, rate: float, floating: float,
                    total_minus: float, total_plus: float, total_base: float) -> str:
    if cfg.fixed_period_years == 0:
        return (
            f"Stays at the floating rate ({floating * 100:.2f}%) the whole way. "
            "Cheapest if rates fall; most exposed if rates rise."
        )
    direction = "below" if rate < floating else "above"
    swing_down = total_base - total_minus
    swing_up = total_plus - total_base
    return (
        f"Locks the rate at {rate * 100:.2f}% for {cfg.fixed_period_years} year(s), "
        f"{direction} the current floating rate of {floating * 100:.2f}%. "
        f"If floating falls 1% you'd save about ${swing_down:,.0f}; "
        f"if it rises 1% you'd pay about ${swing_up:,.0f} extra."
    )


# --- Compound growth ---------------------------------------------------------

def compound_growth(
    principal: float,
    annual_rate: float,
    years: int,
    monthly_contrib: float = 0.0,
    contrib_start_month: int = 0,
) -> float:
    """Future value of a lump sum + optional monthly contributions, compounded monthly.

    ``contrib_start_month`` lets contributions begin partway through the horizon —
    used by the waterfall to model "start investing once the emergency fund is full".
    """
    if years <= 0:
        return principal
    months = years * 12
    contrib_months = max(0, months - max(0, contrib_start_month))
    if annual_rate == 0:
        return principal + monthly_contrib * contrib_months
    r = annual_rate / 12
    factor = (1 + r) ** months
    fv_lump = principal * factor
    if contrib_months == 0 or monthly_contrib == 0:
        return fv_lump
    fv_contrib = monthly_contrib * ((1 + r) ** contrib_months - 1) / r
    return fv_lump + fv_contrib


# --- Taxable-investing leaf --------------------------------------------------

# Split of taxable-investing surplus between a 12-month term deposit and an
# index fund. The waterfall has already decided how much money reaches the
# leaf; the leaf only decides TD vs index per risk profile.
_RISK_SPLITS: dict[RiskLevel, tuple[float, float]] = {
    "low":    (0.70, 0.30),
    "medium": (0.40, 0.60),
    "high":   (0.15, 0.85),
}


def _providers_for(term_id: str, snapshot: MarketSnapshot) -> list[ProviderSuggestion]:
    if term_id == "emergency-fund":
        rows = materialise(HIGH_YIELD_SAVINGS, snapshot.savings.high_yield_savings)
    elif term_id == "term-deposit":
        rows = materialise(TERM_DEPOSIT_12M, snapshot.savings.term_deposit_12m)
    elif term_id == "index-fund":
        rows = materialise(INDEX_FUND, snapshot.index_fund_avg_return)
    else:
        return []
    return [ProviderSuggestion(**r) for r in rows]


def recommend_allocation_leaf(
    lump: float,
    monthly: float,
    risk: RiskLevel,
    horizon_years: int,
    snapshot: MarketSnapshot,
    contrib_start_month: int = 0,
) -> list[AllocationSlice]:
    """Split taxable-investing surplus between a 12-month term deposit and an index fund.

    Caller-controlled — no emergency-fund logic, no risk-based fraction-of-income
    sizing. The waterfall has already determined how much money should reach this
    leaf; the leaf only decides the TD vs index split per ``risk``.
    """
    if lump <= 0 and monthly <= 0:
        return []

    td_share, idx_share = _RISK_SPLITS[risk]
    td_lump = lump * td_share
    idx_lump = lump * idx_share
    td_monthly = monthly * td_share
    idx_monthly = monthly * idx_share

    td_rate = snapshot.savings.term_deposit_12m
    idx_rate = snapshot.index_fund_avg_return

    slices: list[AllocationSlice] = []

    if td_lump > 0 or td_monthly > 0:
        projected = compound_growth(
            principal=td_lump,
            annual_rate=td_rate,
            years=horizon_years,
            monthly_contrib=td_monthly,
            contrib_start_month=contrib_start_month,
        )
        slices.append(AllocationSlice(
            label="12-month term deposit",
            term_id="term-deposit",
            amount=round(td_lump, 2),
            monthly_contribution=round(td_monthly, 2),
            contribution_starts_month=contrib_start_month,
            vehicle="12-month term deposit",
            current_rate=td_rate,
            projected_value_at_horizon=round(projected, 2),
            rationale=(
                f"Locked-in {td_rate * 100:.2f}% return — predictable and principal-safe. "
                f"Sized to a {risk}-risk profile."
            ),
            suggested_providers=_providers_for("term-deposit", snapshot),
        ))

    if idx_lump > 0 or idx_monthly > 0:
        projected = compound_growth(
            principal=idx_lump,
            annual_rate=idx_rate,
            years=horizon_years,
            monthly_contrib=idx_monthly,
            contrib_start_month=contrib_start_month,
        )
        slices.append(AllocationSlice(
            label="Diversified index fund",
            term_id="index-fund",
            amount=round(idx_lump, 2),
            monthly_contribution=round(idx_monthly, 2),
            contribution_starts_month=contrib_start_month,
            vehicle="Low-fee global index fund",
            current_rate=idx_rate,
            projected_value_at_horizon=round(projected, 2),
            rationale=(
                f"Long-run average return ~{idx_rate * 100:.2f}% — volatile year-to-year, "
                f"the engine of growth over a {horizon_years}-year horizon."
            ),
            suggested_providers=_providers_for("index-fund", snapshot),
        ))

    return slices
