from datetime import datetime, timezone

import pytest

from app.logic.finance import (
    compare_loan_strategies,
    compound_growth,
    monthly_payment,
    recommend_allocation_leaf,
    remaining_balance,
)
from app.models.loan import LoanCompareRequest
from app.models.rates import MarketSnapshot, MortgageRates, SavingsRates


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        mortgage=MortgageRates(
            fixed_1y=0.0625, fixed_2y=0.0610, fixed_3y=0.0599,
            fixed_5y=0.0615, floating=0.0700,
        ),
        savings=SavingsRates(
            high_yield_savings=0.0425,
            term_deposit_6m=0.0480,
            term_deposit_12m=0.0510,
            term_deposit_24m=0.0490,
        ),
        index_fund_avg_return=0.0750,
        inflation=0.0290,
        central_bank_rate=0.0425,
        source="mock",
        fetched_at=datetime.now(timezone.utc),
    )


# --- monthly_payment ----------------------------------------------------------

def test_monthly_payment_known_value():
    # $500k @ 6% / 30y is a textbook example: ~$2,997.75
    assert monthly_payment(500_000, 0.06, 30) == pytest.approx(2997.75, abs=0.5)


def test_monthly_payment_zero_rate():
    assert monthly_payment(120_000, 0.0, 10) == pytest.approx(1_000.0)


def test_monthly_payment_zero_principal():
    assert monthly_payment(0, 0.05, 30) == 0.0


# --- remaining_balance --------------------------------------------------------

def test_remaining_balance_at_term_is_zero():
    assert remaining_balance(500_000, 0.06, 30, 30 * 12) == pytest.approx(0.0, abs=1e-6)


def test_remaining_balance_at_zero_is_principal():
    assert remaining_balance(500_000, 0.06, 30, 0) == 500_000


def test_remaining_balance_monotonic_decreasing():
    prev = 500_000
    for m in (12, 60, 120, 240, 359):
        cur = remaining_balance(500_000, 0.06, 30, m)
        assert cur < prev
        prev = cur


# --- compound_growth ----------------------------------------------------------

def test_compound_growth_lump_sum_known_value():
    # 10k at 7% for 10y, monthly compounding ≈ 20,096.61
    assert compound_growth(10_000, 0.07, 10) == pytest.approx(20_096.61, abs=1.0)


def test_compound_growth_zero_rate_with_contributions():
    fv = compound_growth(1_000, 0.0, 5, monthly_contrib=100)
    assert fv == pytest.approx(1_000 + 100 * 60)


def test_compound_growth_zero_years():
    assert compound_growth(5_000, 0.05, 0) == 5_000


def test_compound_growth_with_delayed_contributions():
    fv_now   = compound_growth(0, 0.07, 10, monthly_contrib=500, contrib_start_month=0)
    fv_later = compound_growth(0, 0.07, 10, monthly_contrib=500, contrib_start_month=24)
    assert fv_later < fv_now


# --- compare_loan_strategies --------------------------------------------------

def test_compare_returns_one_per_strategy():
    snap = _snapshot()
    req = LoanCompareRequest(principal=500_000, term_years=30,
                             strategies=["fixed_1y", "fixed_3y", "fixed_5y", "floating"])
    resp = compare_loan_strategies(req, snap)
    assert {r.strategy for r in resp.results} == {"fixed_1y", "fixed_3y", "fixed_5y", "floating"}


def test_compare_best_strategy_has_lowest_total_interest():
    snap = _snapshot()
    req = LoanCompareRequest(principal=500_000, term_years=30,
                             strategies=["fixed_1y", "fixed_3y", "fixed_5y", "floating"])
    resp = compare_loan_strategies(req, snap)
    best = next(r for r in resp.results if r.strategy == resp.best_strategy)
    assert best.projected_total_interest == min(r.projected_total_interest for r in resp.results)


def test_compare_sensitivity_is_monotonic():
    snap = _snapshot()
    req = LoanCompareRequest(principal=500_000, term_years=30, strategies=["fixed_3y"])
    resp = compare_loan_strategies(req, snap)
    r = resp.results[0]
    assert r.sensitivity_minus_1pct_total_interest < r.projected_total_interest < r.sensitivity_plus_1pct_total_interest


def test_compare_balance_after_fixed_matches_independent_calc():
    snap = _snapshot()
    req = LoanCompareRequest(principal=500_000, term_years=30, strategies=["fixed_5y"])
    resp = compare_loan_strategies(req, snap)
    r = resp.results[0]
    expected_balance = remaining_balance(500_000, snap.mortgage.fixed_5y, 30, 60)
    assert r.balance_after_fixed == pytest.approx(expected_balance, abs=0.5)


# --- recommend_allocation_leaf -----------------------------------------------

def test_leaf_zero_inputs_returns_empty():
    snap = _snapshot()
    assert recommend_allocation_leaf(0, 0, "medium", 10, snap) == []


def test_leaf_low_risk_skews_term_deposit():
    snap = _snapshot()
    slices = recommend_allocation_leaf(10_000, 0, "low", 10, snap)
    td = next(s for s in slices if s.term_id == "term-deposit")
    idx = next(s for s in slices if s.term_id == "index-fund")
    assert td.amount > idx.amount


def test_leaf_high_risk_skews_index_fund():
    snap = _snapshot()
    slices = recommend_allocation_leaf(10_000, 0, "high", 10, snap)
    td = next(s for s in slices if s.term_id == "term-deposit")
    idx = next(s for s in slices if s.term_id == "index-fund")
    assert idx.amount > td.amount


def test_leaf_lump_sum_amounts_sum_to_total():
    snap = _snapshot()
    slices = recommend_allocation_leaf(10_000, 0, "medium", 10, snap)
    total = sum(s.amount for s in slices)
    assert total == pytest.approx(10_000, abs=0.01)


def test_leaf_provider_suggestions_present():
    snap = _snapshot()
    slices = recommend_allocation_leaf(10_000, 200, "medium", 10, snap)
    for s in slices:
        assert s.suggested_providers, f"slice {s.term_id} should have providers"
        for p in s.suggested_providers:
            assert p.name and p.why
            assert p.indicative_rate >= 0


def test_leaf_monthly_only_produces_zero_lump_slices():
    """When there's no lump sum, slices still appear if there's a monthly stream."""
    snap = _snapshot()
    slices = recommend_allocation_leaf(0, 500, "high", 10, snap)
    assert len(slices) == 2
    for s in slices:
        assert s.amount == 0
        assert s.monthly_contribution > 0
        assert s.projected_value_at_horizon > 0


def test_leaf_contrib_start_month_propagates():
    snap = _snapshot()
    slices = recommend_allocation_leaf(0, 500, "medium", 10, snap, contrib_start_month=6)
    for s in slices:
        assert s.contribution_starts_month == 6
