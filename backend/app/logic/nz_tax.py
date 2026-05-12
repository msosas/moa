"""New Zealand tax + KiwiSaver helpers — pure functions, no I/O.

All rates are decimals (e.g. ``0.105`` for 10.5%); all amounts are NZD; all income
figures are annual unless explicitly named otherwise.

Sources of truth (verified at implementation time):
- IRD PAYE brackets effective 1 April 2025 — full-year application of the
  31 July 2024 threshold changes.
- KiwiSaver Act 2006: minimum employer contribution 3%; Member Tax Credit is
  $0.50 per $1 of member contribution, capped at $521.43 per year (requires
  contributing $1,042.86 to receive the full credit).
- PIE (Portfolio Investment Entity) Prescribed Investor Rates: 10.5%, 17.5%, 28%.
"""

from __future__ import annotations

import math

# --- PAYE — FY 2025/26 (1 April 2025 to 31 March 2026) ----------------------
PAYE_BRACKETS_FY26: list[tuple[float, float]] = [
    (15_600,   0.105),
    (53_500,   0.175),
    (78_100,   0.30),
    (180_000,  0.33),
    (math.inf, 0.39),
]

# --- ACC Earners' Levy ------------------------------------------------------
ACC_EARNERS_LEVY_RATE = 0.0146
ACC_EARNERS_LEVY_MAX = 152_790.0

# --- KiwiSaver --------------------------------------------------------------
KIWISAVER_EMPLOYEE_RATES: tuple[float, ...] = (0.03, 0.04, 0.06, 0.08, 0.10)
KIWISAVER_DEFAULT_EMPLOYEE = 0.03
KIWISAVER_DEFAULT_EMPLOYER = 0.03

MTC_RATE = 0.50
MTC_ANNUAL_MAX = 521.43
MTC_QUALIFYING_CONTRIB = 1_042.86

# --- PIE / RWT --------------------------------------------------------------
PIE_TIERS: tuple[float, float, float] = (0.105, 0.175, 0.28)
RWT_DEFAULT = 0.33


# --- PAYE -------------------------------------------------------------------

def paye_annual_tax(gross_annual: float) -> float:
    """Annual PAYE owed on a gross annual income, using FY26 brackets.

    Excludes ACC earners' levy — see :func:`acc_earners_levy`.
    """
    if gross_annual <= 0:
        return 0.0
    tax = 0.0
    lower = 0.0
    for upper, rate in PAYE_BRACKETS_FY26:
        slice_amount = max(0.0, min(gross_annual, upper) - lower)
        tax += slice_amount * rate
        if gross_annual <= upper:
            break
        lower = upper
    return tax


def acc_earners_levy(gross_annual: float) -> float:
    """ACC earners' levy on salary/wages, capped at the FY26 ceiling."""
    if gross_annual <= 0:
        return 0.0
    return min(gross_annual, ACC_EARNERS_LEVY_MAX) * ACC_EARNERS_LEVY_RATE


def paye_net_annual(gross_annual: float) -> float:
    """Net annual income after PAYE and ACC earners' levy."""
    return gross_annual - paye_annual_tax(gross_annual) - acc_earners_levy(gross_annual)


def paye_net_monthly(gross_annual: float) -> float:
    return paye_net_annual(gross_annual) / 12


def marginal_rate(gross_annual: float) -> float:
    """Marginal PAYE rate at the user's current income (ignores ACC)."""
    if gross_annual <= 0:
        return PAYE_BRACKETS_FY26[0][1]
    for upper, rate in PAYE_BRACKETS_FY26:
        if gross_annual <= upper:
            return rate
    return PAYE_BRACKETS_FY26[-1][1]


# --- KiwiSaver --------------------------------------------------------------

def kiwisaver_employee_contribution(gross_annual: float, rate: float) -> float:
    """Annual employee KiwiSaver contribution at the chosen rate."""
    if gross_annual <= 0 or rate <= 0:
        return 0.0
    return gross_annual * rate


def kiwisaver_employer_contribution(
    gross_annual: float, rate: float = KIWISAVER_DEFAULT_EMPLOYER,
) -> float:
    """Annual employer KiwiSaver contribution (3% statutory minimum)."""
    if gross_annual <= 0 or rate <= 0:
        return 0.0
    return gross_annual * rate


def member_tax_credit(annual_member_contribution: float) -> float:
    """Annual KiwiSaver Member Tax Credit (MTC).

    Piecewise linear: $0.50 per $1 contributed up to the qualifying amount
    ($1,042.86), capped at $521.43. Members must contribute at least the
    qualifying amount to receive the full credit; partial credits are pro-rated.
    """
    if annual_member_contribution <= 0:
        return 0.0
    if annual_member_contribution >= MTC_QUALIFYING_CONTRIB:
        return MTC_ANNUAL_MAX
    return annual_member_contribution * MTC_RATE


# --- After-tax returns ------------------------------------------------------

def after_pie_return(nominal_return: float, pir: float) -> float:
    """Return net of PIE tax — PIE income is taxed at the chosen PIR (cap 28%)."""
    return nominal_return * (1 - pir)


def after_rwt_return(nominal_return: float, rwt: float = RWT_DEFAULT) -> float:
    """Return net of Resident Withholding Tax (non-PIE interest, e.g. term deposits)."""
    return nominal_return * (1 - rwt)
