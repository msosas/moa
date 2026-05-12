"""Holistic financial-order-of-operations engine.

Takes a :class:`FinancialProfile` and a :class:`MarketSnapshot`; returns a
prioritized :class:`RecommendedPlan`. Each step consumes from a shared
``(remaining_lump, remaining_monthly)`` pool so amounts always reconcile.

Step order (each only emitted if its trigger fires):

1. **Starter emergency fund** — 1 × monthly expenses.
2. **High-interest debt** — non-mortgage debt above 8% APR (avalanche).
3. **KiwiSaver employer match** — bump employee rate to 3% if under.
4. **Full emergency fund** — 3 / 4 / 6 months by job stability, +1 per dependent.
5. **Mortgage vs invest** — after-tax mortgage rate vs PIR-adjusted index return.
6. **KiwiSaver beyond match** — bump rate further if PIE beats RWT.
7. **Taxable investing** — leaf split between term deposit and index fund.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.logic import nz_tax
from app.logic.finance import (
    compare_loan_strategies,
    compound_growth,
    monthly_payment,
    recommend_allocation_leaf,
    remaining_balance,
)
from app.models.loan import LoanCompareRequest, LoanCompareResponse
from app.models.profile import (
    CashFlowSummary,
    FinancialProfile,
    HorizonProjection,
    PlanStep,
    RationaleBlock,
    RecommendedPlan,
    StepKind,
)
from app.models.rates import MarketSnapshot

HIGH_INTEREST_THRESHOLD = 0.08
MORTGAGE_RISK_PREMIUM = 0.015
_EF_MONTHS_BY_STABILITY: dict[str, int] = {"stable": 3, "moderate": 4, "unstable": 6}
_MAX_EF_MONTHS = 9
_STARTER_EF_MONTHS = 1


@dataclass
class _State:
    profile: FinancialProfile
    snapshot: MarketSnapshot
    remaining_lump: float
    remaining_monthly: float
    current_ef: float
    employee_rate: float
    priority: int = 1
    steps: list[PlanStep] = field(default_factory=list)

    def next_priority(self) -> int:
        p = self.priority
        self.priority += 1
        return p


# --- Step helpers ------------------------------------------------------------

def _starter_ef_step(state: _State) -> None:
    monthly_exp = state.profile.total_monthly_expenses
    if monthly_exp <= 0:
        return
    target = monthly_exp * _STARTER_EF_MONTHS
    gap = target - state.current_ef
    if gap <= 0:
        return

    from_lump = min(gap, state.remaining_lump)
    state.remaining_lump -= from_lump
    state.current_ef += from_lump
    gap_after_lump = max(0.0, target - state.current_ef)

    monthly_alloc = 0.0
    months_to_fill = 0
    if gap_after_lump > 0 and state.remaining_monthly > 0:
        monthly_alloc = min(state.remaining_monthly, gap_after_lump)
        months_to_fill = math.ceil(gap_after_lump / monthly_alloc) if monthly_alloc > 0 else 0
        state.remaining_monthly -= monthly_alloc
        state.current_ef += monthly_alloc * months_to_fill

    state.steps.append(PlanStep(
        priority=state.next_priority(),
        band="must_do",
        kind=StepKind.STARTER_EMERGENCY_FUND,
        action=(
            f"Set aside ${target:,.0f} — that's one month of your usual expenses — in a "
            "savings account, before doing anything else."
        ),
        amount_today=round(from_lump, 2),
        monthly_amount=round(monthly_alloc, 2),
        expected_outcome={
            "starter_ef_target": round(target, 2),
            "months_to_full_starter": float(months_to_fill),
        },
        rationale=RationaleBlock(
            primary_reason=(
                "If something unexpected happens — a car repair, a vet bill, a few weeks "
                "between jobs — and you don't have cash for it, you end up borrowing at high "
                "rates and undoing everything else. Get this small buffer in place first."
            ),
            numeric_facts={
                "monthly_expenses": round(monthly_exp, 2),
                "target": round(target, 2),
                "savings_rate_apr": state.snapshot.savings.high_yield_savings,
            },
            citations=["Foundation: a starter cash buffer before any other priority."],
        ),
        confidence="high",
    ))


def _high_interest_debt_step(state: _State) -> None:
    targets = [
        d for d in state.profile.debts
        if d.kind != "mortgage" and d.annual_rate > HIGH_INTEREST_THRESHOLD and d.balance > 0
    ]
    if not targets:
        return
    targets.sort(key=lambda d: d.annual_rate, reverse=True)
    total_balance = sum(d.balance for d in targets)
    worst = targets[0]

    from_lump = min(total_balance, state.remaining_lump)
    state.remaining_lump -= from_lump
    leftover = max(0.0, total_balance - from_lump)

    # Direct up to 70% of remaining monthly surplus at the debt, capped at the
    # amount that would clear leftover in ~3 months — never over-allocate.
    monthly_attack = 0.0
    if leftover > 0 and state.remaining_monthly > 0:
        monthly_attack = min(state.remaining_monthly * 0.7, leftover / 3)
        state.remaining_monthly -= monthly_attack

    payoff_months = 0
    if monthly_attack > 0 and leftover > 0:
        avg_rate = sum(d.annual_rate * d.balance for d in targets) / total_balance
        r = avg_rate / 12
        if r > 0 and monthly_attack > leftover * r:
            payoff_months = math.ceil(
                math.log(monthly_attack / (monthly_attack - leftover * r)) / math.log(1 + r)
            )
        else:
            payoff_months = math.ceil(leftover / monthly_attack)

    state.steps.append(PlanStep(
        priority=state.next_priority(),
        band="must_do",
        kind=StepKind.HIGH_INTEREST_DEBT,
        action=(
            f"Pay off the ${total_balance:,.0f} you owe on expensive debt — start with "
            f"the {worst.kind.replace('_', ' ')}, which is charging you "
            f"{worst.annual_rate * 100:.2f}% a year."
        ),
        amount_today=round(from_lump, 2),
        monthly_amount=round(monthly_attack, 2),
        expected_outcome={
            "total_high_interest_balance": round(total_balance, 2),
            "remaining_after_lump": round(leftover, 2),
            "payoff_months": float(payoff_months),
        },
        rationale=RationaleBlock(
            primary_reason=(
                f"Every dollar you put against debt that costs {worst.annual_rate * 100:.2f}% "
                "a year is like earning that same rate, risk-free. Nothing else you could do "
                "with the money is that good a deal."
            ),
            numeric_facts={
                "highest_rate": worst.annual_rate,
                "total_balance": round(total_balance, 2),
                "monthly_attack": round(monthly_attack, 2),
            },
            citations=["Pay off the most expensive debt first (avalanche method)."],
        ),
        confidence="high",
    ))


def _kiwisaver_employer_match_step(state: _State) -> None:
    if not state.profile.is_employed or state.profile.kiwisaver is None:
        return
    if state.employee_rate >= nz_tax.KIWISAVER_DEFAULT_EMPLOYEE:
        return
    gross = state.profile.gross_annual_income
    target_rate = nz_tax.KIWISAVER_DEFAULT_EMPLOYEE
    extra_employee_monthly = (target_rate - state.employee_rate) * gross / 12
    employer_monthly = state.profile.kiwisaver.employer_rate * gross / 12

    # Bumping employee_rate reduces take-home, so deduct from surplus to keep
    # the accounting honest. Even if surplus is tight, this is the highest-ROI
    # dollar in the plan — we don't gate on remaining_monthly.
    state.remaining_monthly = max(0.0, state.remaining_monthly - extra_employee_monthly)
    state.employee_rate = target_rate

    state.steps.append(PlanStep(
        priority=state.next_priority(),
        band="must_do",
        kind=StepKind.KIWISAVER_EMPLOYER_MATCH,
        action=(
            f"Raise your KiwiSaver contribution from "
            f"{state.profile.kiwisaver.employee_rate * 100:.0f}% to {target_rate * 100:.0f}% of "
            f"your pay. Your employer adds another ${employer_monthly:,.0f} a month on top — "
            "that's money you'd otherwise leave behind."
        ),
        amount_today=0.0,
        monthly_amount=round(extra_employee_monthly, 2),
        expected_outcome={
            "extra_employee_monthly": round(extra_employee_monthly, 2),
            "employer_monthly_unlocked": round(employer_monthly, 2),
            "annual_free_money": round(employer_monthly * 12, 2),
        },
        rationale=RationaleBlock(
            primary_reason=(
                "If you put in less than 3%, your employer is allowed to put in less too. "
                "Going to 3% unlocks the full match — every dollar you contribute is matched "
                "dollar-for-dollar by your employer. There's no better return on those dollars."
            ),
            numeric_facts={
                "current_rate": state.profile.kiwisaver.employee_rate,
                "target_rate": target_rate,
                "employer_match_rate": state.profile.kiwisaver.employer_rate,
                "gross_annual_income": gross,
            },
            citations=["Employers in NZ match KiwiSaver up to 3% if you contribute 3% yourself."],
        ),
        confidence="high",
    ))


def _full_ef_step(state: _State) -> None:
    monthly_exp = state.profile.total_monthly_expenses
    if monthly_exp <= 0:
        return
    base_months = _EF_MONTHS_BY_STABILITY[state.profile.job_stability]
    months = min(_MAX_EF_MONTHS, base_months + state.profile.dependents)
    target = monthly_exp * months
    gap = target - state.current_ef
    if gap <= 0:
        return

    from_lump = min(gap, state.remaining_lump)
    state.remaining_lump -= from_lump
    state.current_ef += from_lump
    gap_after_lump = max(0.0, target - state.current_ef)

    monthly_alloc = 0.0
    months_to_fill = 0
    if gap_after_lump > 0 and state.remaining_monthly > 0:
        # Up to half the remaining surplus — leaves room for later priorities.
        monthly_alloc = min(state.remaining_monthly * 0.5, gap_after_lump)
        state.remaining_monthly -= monthly_alloc
        months_to_fill = math.ceil(gap_after_lump / monthly_alloc) if monthly_alloc > 0 else 0
        state.current_ef += monthly_alloc * months_to_fill

    state.steps.append(PlanStep(
        priority=state.next_priority(),
        band="recommended",
        kind=StepKind.FULL_EMERGENCY_FUND,
        action=(
            f"Grow your savings buffer to ${target:,.0f} — about {months} months of your "
            "usual expenses — and keep it in an easy-to-access savings account."
        ),
        amount_today=round(from_lump, 2),
        monthly_amount=round(monthly_alloc, 2),
        expected_outcome={
            "target": round(target, 2),
            "months_to_target": float(months_to_fill),
        },
        rationale=RationaleBlock(
            primary_reason=(
                f"With a {state.profile.job_stability} income and "
                f"{state.profile.dependents} people relying on you, {months} months of "
                "expenses in cash is the size of safety net most advisors recommend. "
                "It's there for emergencies — not meant to grow long-term."
            ),
            numeric_facts={
                "monthly_expenses": round(monthly_exp, 2),
                "target_months": float(months),
                "savings_rate_apr": state.snapshot.savings.high_yield_savings,
            },
            citations=["Full safety net sized to job stability and dependents."],
        ),
        confidence="high",
    ))


def _mortgage_vs_invest_step(state: _State) -> LoanCompareResponse | None:
    if not state.profile.has_mortgage:
        return None
    if state.remaining_monthly <= 0:
        return None
    mortgage = state.profile.mortgage
    assert mortgage is not None

    req = LoanCompareRequest(
        principal=mortgage.balance,
        term_years=mortgage.term_years_remaining,
        strategies=["fixed_1y", "fixed_2y", "fixed_3y", "fixed_5y", "floating"],
    )
    cmp = compare_loan_strategies(req, state.snapshot)
    best = next(r for r in cmp.results if r.strategy == cmp.best_strategy)

    # The user's current monthly payment — auto-derived from balance/rate/term if absent.
    current_monthly = mortgage.monthly_payment or monthly_payment(
        mortgage.balance, mortgage.annual_rate, mortgage.term_years_remaining,
    )
    fixed_until_str = mortgage.fixed_until.isoformat() if mortgage.fixed_until else None
    refix_clause = (
        f"When your current fix ends on {fixed_until_str}, "
        if fixed_until_str else "When your current fix ends, "
    )
    surplus = state.profile.monthly_surplus

    mortgage_rate = mortgage.annual_rate
    pir = state.profile.kiwisaver.pir if state.profile.kiwisaver else nz_tax.PIE_TIERS[-1]
    after_pie_index = nz_tax.after_pie_return(state.snapshot.index_fund_avg_return, pir)
    invest_beats_mortgage = (after_pie_index - MORTGAGE_RISK_PREMIUM) > mortgage_rate

    risk_adjusted_return = after_pie_index - MORTGAGE_RISK_PREMIUM
    if invest_beats_mortgage:
        extra_payment = 0.0
        total_monthly = best.monthly_payment_during_fixed
        change_vs_current = total_monthly - current_monthly
        action = (
            f"Don't put surplus toward your mortgage — invest it instead. "
            f"{refix_clause}refix to the {best.label.lower()} at {best.initial_rate * 100:.2f}%; "
            f"your minimum repayment becomes ${total_monthly:,.2f} a month "
            f"(${abs(change_vs_current):,.2f} less than the ${current_monthly:,.0f} you pay today). "
            "Pay just that minimum and direct everything else into investing. "
            f"Investments should earn around {after_pie_index * 100:.1f}% a year after tax on "
            f"average — comfortably more than the {mortgage_rate * 100:.2f}% your mortgage "
            "costs, even after allowing for stock-market ups and downs."
        )
        monthly_amount = 0.0
        band = "recommended"
    else:
        extra_payment = state.remaining_monthly * 0.5
        state.remaining_monthly -= extra_payment
        total_monthly = best.monthly_payment_during_fixed + extra_payment
        change_vs_current = total_monthly - current_monthly
        share_of_surplus_pct = (extra_payment / surplus * 100) if surplus > 0 else 0.0
        action = (
            f"Put an extra ${extra_payment:,.2f} a month on your mortgage — that's "
            f"{share_of_surplus_pct:.0f}% of your ${surplus:,.2f} monthly surplus. "
            f"{refix_clause}you'll refix to the {best.label.lower()} at "
            f"{best.initial_rate * 100:.2f}%, so your minimum repayment becomes "
            f"${best.monthly_payment_during_fixed:,.2f}. Adding the extra on top, your total "
            f"monthly mortgage payment is ${total_monthly:,.2f} (vs ${current_monthly:,.0f} "
            "today). Why this beats investing: your mortgage rate "
            f"({mortgage_rate * 100:.2f}%) is a guaranteed saving on every extra dollar you "
            f"put in. Investing might average {after_pie_index * 100:.1f}% after tax but with "
            "real ups and downs along the way — once you allow a buffer for that risk "
            f"(≈{risk_adjusted_return * 100:.1f}% net), paying down comes out ahead."
        )
        monthly_amount = round(extra_payment, 2)
        band = "must_do"

    expected_outcome = {
        "current_monthly_payment": round(current_monthly, 2),
        "new_minimum_payment": best.monthly_payment_during_fixed,
        "extra_per_month": round(extra_payment, 2),
        "total_monthly_payment": round(total_monthly, 2),
        "change_vs_current": round(change_vs_current, 2),
        "best_strategy_total_interest": best.projected_total_interest,
        "sensitivity_minus_1pct": best.sensitivity_minus_1pct_total_interest,
        "sensitivity_plus_1pct": best.sensitivity_plus_1pct_total_interest,
    }
    numeric_facts = {
        "current_monthly_payment": round(current_monthly, 2),
        "new_minimum_payment": best.monthly_payment_during_fixed,
        "extra_per_month": round(extra_payment, 2),
        "total_monthly_payment": round(total_monthly, 2),
        "mortgage_rate": mortgage_rate,
        "after_pie_index_return": after_pie_index,
        "risk_premium": MORTGAGE_RISK_PREMIUM,
        "best_strategy_total_interest": best.projected_total_interest,
    }
    references = [best.strategy]
    if fixed_until_str:
        # Surface the date through ``references`` so the frontend can show it as
        # text — ``expected_outcome`` and ``numeric_facts`` only carry floats.
        references.append(f"fixed_until:{fixed_until_str}")

    state.steps.append(PlanStep(
        priority=state.next_priority(),
        band=band,
        kind=StepKind.MORTGAGE_VS_INVEST,
        action=action,
        amount_today=0.0,
        monthly_amount=monthly_amount,
        expected_outcome=expected_outcome,
        rationale=RationaleBlock(
            primary_reason=(
                f"Your mortgage costs {mortgage_rate * 100:.2f}% a year — a guaranteed cost. "
                f"Investments could earn around {after_pie_index * 100:.1f}% on average after "
                "tax, but with ups and downs along the way. "
                + (
                    "The gap is wide enough that investing still comes out ahead even after "
                    "allowing for that risk."
                    if invest_beats_mortgage
                    else "Once you allow for that risk (about a 1.5% buffer), the safer return "
                    "from paying down the mortgage wins."
                )
            ),
            numeric_facts=numeric_facts,
            citations=["Mortgage-vs-invest decision based on after-tax return and risk premium."],
        ),
        references=references,
        confidence="high" if abs(after_pie_index - mortgage_rate) > 0.02 else "medium",
    ))
    return cmp


def _kiwisaver_beyond_match_step(state: _State) -> None:
    if state.profile.kiwisaver is None or not state.profile.is_employed:
        return
    if state.remaining_monthly <= 0 or state.employee_rate >= 0.10:
        return
    pir = state.profile.kiwisaver.pir
    nominal_return = state.snapshot.index_fund_avg_return
    ks_after_tax = nz_tax.after_pie_return(nominal_return, pir)
    taxable_after_rwt = nz_tax.after_rwt_return(nominal_return)
    if ks_after_tax < taxable_after_rwt:
        return

    next_rates = [r for r in nz_tax.KIWISAVER_EMPLOYEE_RATES if r > state.employee_rate]
    if not next_rates:
        return
    next_rate = next_rates[0]
    extra_monthly = (next_rate - state.employee_rate) * state.profile.gross_annual_income / 12
    if extra_monthly > state.remaining_monthly:
        return
    state.remaining_monthly -= extra_monthly
    state.employee_rate = next_rate

    state.steps.append(PlanStep(
        priority=state.next_priority(),
        band="optional",
        kind=StepKind.KIWISAVER_BEYOND_MATCH,
        action=(
            f"Lift your KiwiSaver contribution to {next_rate * 100:.0f}% of your pay — "
            f"that's about ${extra_monthly:,.0f} more a month coming off your take-home. "
            "You can't touch this money until you're 65, but it grows a bit faster than "
            "regular investments because the tax on the returns is lower."
        ),
        amount_today=0.0,
        monthly_amount=round(extra_monthly, 2),
        expected_outcome={
            "ks_after_pie_return": ks_after_tax,
            "taxable_after_rwt_return": taxable_after_rwt,
            "new_employee_rate": next_rate,
        },
        rationale=RationaleBlock(
            primary_reason=(
                f"Returns earned inside KiwiSaver are taxed at most {pir * 100:.1f}% — "
                f"compared to {nz_tax.RWT_DEFAULT * 100:.0f}% on most everyday investments. "
                "Same money in, more left over after tax."
            ),
            numeric_facts={
                "ks_after_pie_return": ks_after_tax,
                "taxable_after_rwt_return": taxable_after_rwt,
                "extra_monthly": round(extra_monthly, 2),
            },
            citations=["KiwiSaver taxes returns at a lower rate than money invested directly."],
        ),
        confidence="medium",
    ))


def _taxable_investing_step(state: _State) -> None:
    if state.remaining_lump <= 0 and state.remaining_monthly <= 0:
        return
    slices = recommend_allocation_leaf(
        lump=state.remaining_lump,
        monthly=state.remaining_monthly,
        risk=state.profile.risk_tolerance,
        horizon_years=state.profile.time_horizon_years,
        snapshot=state.snapshot,
    )
    if not slices:
        return

    providers = [p for s in slices for p in s.suggested_providers]
    projected = sum(s.projected_value_at_horizon for s in slices)

    state.steps.append(PlanStep(
        priority=state.next_priority(),
        band="optional",
        kind=StepKind.TAXABLE_INVESTING,
        action=(
            f"Direct the remaining ${state.remaining_monthly:,.0f} of your monthly surplus into "
            "investments — split between a one-year term deposit (the safer half) and a global "
            f"share fund (the growth half). The split matches your "
            f"{state.profile.risk_tolerance}-risk preference."
        ),
        amount_today=round(state.remaining_lump, 2),
        monthly_amount=round(state.remaining_monthly, 2),
        expected_outcome={
            "td_amount":   next((s.amount for s in slices if s.term_id == "term-deposit"), 0),
            "idx_amount":  next((s.amount for s in slices if s.term_id == "index-fund"), 0),
            "td_monthly":  next((s.monthly_contribution for s in slices if s.term_id == "term-deposit"), 0),
            "idx_monthly": next((s.monthly_contribution for s in slices if s.term_id == "index-fund"), 0),
            "projected_at_horizon": round(projected, 2),
        },
        rationale=RationaleBlock(
            primary_reason=(
                "With the important stuff covered, the rest of your monthly surplus goes into "
                "long-term investments. The mix between safer term deposits and global share "
                "funds reflects how much risk you said you're comfortable with."
            ),
            numeric_facts={
                "td_rate": state.snapshot.savings.term_deposit_12m,
                "index_return": state.snapshot.index_fund_avg_return,
                "horizon_years": float(state.profile.time_horizon_years),
            },
            citations=["A mix of safe and growth investments, sized to your risk preference."],
        ),
        suggested_providers=providers,
        confidence="medium",
    ))
    state.remaining_lump = 0.0
    state.remaining_monthly = 0.0


def _nothing_left_step(state: _State) -> None:
    state.steps.append(PlanStep(
        priority=state.next_priority(),
        band="optional",
        kind=StepKind.NOTHING_LEFT,
        action=(
            "Your top priorities are already funded — review again when your income, "
            "expenses, or goals change."
        ),
        amount_today=0.0,
        monthly_amount=0.0,
        expected_outcome={},
        rationale=RationaleBlock(
            primary_reason=(
                "Emergency fund full, no high-interest debt, KiwiSaver match captured, "
                "and no surplus cash flow to allocate further today."
            ),
        ),
        confidence="medium",
    ))


# --- Horizon projection ------------------------------------------------------

def _project_horizon(
    profile: FinancialProfile, snapshot: MarketSnapshot, steps: list[PlanStep],
) -> HorizonProjection:
    horizon = profile.time_horizon_years

    ef = profile.current_emergency_fund
    for s in steps:
        if s.kind in (StepKind.STARTER_EMERGENCY_FUND, StepKind.FULL_EMERGENCY_FUND):
            ef += s.amount_today + s.monthly_amount * 12

    ks_balance = profile.kiwisaver.balance if profile.kiwisaver else 0.0
    ks_monthly_contrib = 0.0
    ks_after_tax_return = 0.0
    if profile.kiwisaver and profile.is_employed:
        ks_after_tax_return = nz_tax.after_pie_return(
            snapshot.index_fund_avg_return, profile.kiwisaver.pir,
        )
        # Latest employee rate after any bumps.
        current_emp_rate = profile.kiwisaver.employee_rate
        for s in steps:
            if s.kind == StepKind.KIWISAVER_EMPLOYER_MATCH:
                current_emp_rate = nz_tax.KIWISAVER_DEFAULT_EMPLOYEE
            elif s.kind == StepKind.KIWISAVER_BEYOND_MATCH:
                current_emp_rate = s.expected_outcome.get(
                    "new_employee_rate", current_emp_rate,
                )
        total_rate = current_emp_rate + profile.kiwisaver.employer_rate
        ks_monthly_contrib = total_rate * profile.gross_annual_income / 12
    ks_projection = compound_growth(
        ks_balance, ks_after_tax_return, horizon, ks_monthly_contrib,
    ) if profile.kiwisaver else 0.0

    taxable = sum(inv.balance for inv in profile.existing_investments)
    leaf_horizon_value = 0.0
    for s in steps:
        if s.kind == StepKind.TAXABLE_INVESTING:
            leaf_horizon_value = s.expected_outcome.get("projected_at_horizon", 0.0)
    existing_projection = compound_growth(
        taxable, nz_tax.after_rwt_return(snapshot.index_fund_avg_return), horizon,
    )
    taxable_projection = existing_projection + leaf_horizon_value

    debt_remaining = 0.0
    if profile.has_mortgage:
        mortgage = profile.mortgage
        assert mortgage is not None
        months_elapsed = min(horizon, mortgage.term_years_remaining) * 12
        debt_remaining = max(0.0, remaining_balance(
            mortgage.balance, mortgage.annual_rate,
            mortgage.term_years_remaining, months_elapsed,
        ))

    total = ef + ks_projection + taxable_projection - debt_remaining
    return HorizonProjection(
        emergency_fund=round(ef, 2),
        kiwisaver=round(ks_projection, 2),
        taxable_investments=round(taxable_projection, 2),
        debt_remaining=round(debt_remaining, 2),
        total_net_worth=round(total, 2),
    )


# --- Public entrypoint -------------------------------------------------------

def build_plan(profile: FinancialProfile, snapshot: MarketSnapshot) -> RecommendedPlan:
    """Build a prioritized RecommendedPlan from a holistic FinancialProfile."""
    state = _State(
        profile=profile,
        snapshot=snapshot,
        remaining_lump=profile.lump_sum_available,
        remaining_monthly=profile.monthly_surplus,
        current_ef=profile.current_emergency_fund,
        employee_rate=profile.kiwisaver.employee_rate if profile.kiwisaver else 0.0,
    )

    _starter_ef_step(state)
    _high_interest_debt_step(state)
    _kiwisaver_employer_match_step(state)
    _full_ef_step(state)
    _mortgage_vs_invest_step(state)
    _kiwisaver_beyond_match_step(state)
    _taxable_investing_step(state)

    if not state.steps:
        _nothing_left_step(state)

    cash_flow = CashFlowSummary(
        gross_annual_income=round(profile.gross_annual_income, 2),
        net_monthly_income=round(profile.net_monthly_income, 2),
        total_monthly_expenses=round(profile.total_monthly_expenses, 2),
        monthly_surplus=round(profile.monthly_surplus, 2),
        savings_rate=round(profile.savings_rate, 4),
    )
    horizon = _project_horizon(profile, snapshot, state.steps)

    return RecommendedPlan(
        steps=state.steps,
        cash_flow=cash_flow,
        unallocated_lump_sum=round(max(0.0, state.remaining_lump), 2),
        unallocated_monthly=round(max(0.0, state.remaining_monthly), 2),
        horizon_projection=horizon,
        market_snapshot=snapshot,
    )
