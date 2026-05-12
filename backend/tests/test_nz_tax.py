import pytest

from app.logic.nz_tax import (
    ACC_EARNERS_LEVY_MAX,
    ACC_EARNERS_LEVY_RATE,
    KIWISAVER_DEFAULT_EMPLOYER,
    MTC_ANNUAL_MAX,
    MTC_QUALIFYING_CONTRIB,
    PAYE_BRACKETS_FY26,
    PIE_TIERS,
    acc_earners_levy,
    after_pie_return,
    after_rwt_return,
    kiwisaver_employee_contribution,
    kiwisaver_employer_contribution,
    marginal_rate,
    member_tax_credit,
    paye_annual_tax,
    paye_net_annual,
    paye_net_monthly,
)


# --- PAYE -------------------------------------------------------------------

def test_paye_zero_or_negative_income_is_zero():
    assert paye_annual_tax(0) == 0
    assert paye_annual_tax(-1_000) == 0


@pytest.mark.parametrize(
    "income, expected",
    [
        # Inside first bracket — 10.5%
        (10_000, 10_000 * 0.105),
        # Top of first bracket
        (15_600, 15_600 * 0.105),
        # Just into second — 17.5%
        (15_601, 15_600 * 0.105 + 1 * 0.175),
        # Top of second
        (53_500, 15_600 * 0.105 + (53_500 - 15_600) * 0.175),
        # Just into third — 30%
        (53_501, 15_600 * 0.105 + (53_500 - 15_600) * 0.175 + 1 * 0.30),
        # Top of third
        (78_100,
            15_600 * 0.105
            + (53_500 - 15_600) * 0.175
            + (78_100 - 53_500) * 0.30),
        # Just into fourth — 33%
        (78_101,
            15_600 * 0.105
            + (53_500 - 15_600) * 0.175
            + (78_100 - 53_500) * 0.30
            + 1 * 0.33),
        # Top of fourth
        (180_000,
            15_600 * 0.105
            + (53_500 - 15_600) * 0.175
            + (78_100 - 53_500) * 0.30
            + (180_000 - 78_100) * 0.33),
        # Into top bracket — 39%
        (180_001,
            15_600 * 0.105
            + (53_500 - 15_600) * 0.175
            + (78_100 - 53_500) * 0.30
            + (180_000 - 78_100) * 0.33
            + 1 * 0.39),
    ],
)
def test_paye_at_bracket_boundaries(income, expected):
    assert paye_annual_tax(income) == pytest.approx(expected)


@pytest.mark.parametrize(
    "income, expected_rate",
    [
        (0, 0.105),
        (15_600, 0.105),
        (15_601, 0.175),
        (53_500, 0.175),
        (53_501, 0.30),
        (78_100, 0.30),
        (78_101, 0.33),
        (180_000, 0.33),
        (180_001, 0.39),
        (1_000_000, 0.39),
    ],
)
def test_marginal_rate_at_bracket_edges(income, expected_rate):
    assert marginal_rate(income) == expected_rate


def test_paye_brackets_cover_all_income():
    # Sanity: brackets are monotonically increasing on both axes.
    last_upper = -1
    last_rate = -1
    for upper, rate in PAYE_BRACKETS_FY26:
        assert upper > last_upper
        assert rate > last_rate
        last_upper = upper
        last_rate = rate


# --- ACC --------------------------------------------------------------------

def test_acc_levy_zero_for_no_income():
    assert acc_earners_levy(0) == 0
    assert acc_earners_levy(-50) == 0


def test_acc_levy_linear_below_cap():
    assert acc_earners_levy(50_000) == pytest.approx(50_000 * ACC_EARNERS_LEVY_RATE)


def test_acc_levy_caps_at_max():
    at_cap = acc_earners_levy(ACC_EARNERS_LEVY_MAX)
    over_cap = acc_earners_levy(ACC_EARNERS_LEVY_MAX + 100_000)
    assert at_cap == over_cap == pytest.approx(ACC_EARNERS_LEVY_MAX * ACC_EARNERS_LEVY_RATE)


def test_paye_net_monthly_is_annual_over_twelve():
    gross = 80_000
    assert paye_net_monthly(gross) == pytest.approx(paye_net_annual(gross) / 12)


def test_net_below_gross():
    # Net of PAYE + ACC must always be < gross for any positive income.
    for gross in (20_000, 60_000, 90_000, 200_000):
        assert paye_net_annual(gross) < gross


# --- KiwiSaver --------------------------------------------------------------

def test_employee_contribution_proportional():
    assert kiwisaver_employee_contribution(80_000, 0.03) == pytest.approx(2_400)
    assert kiwisaver_employee_contribution(80_000, 0.06) == pytest.approx(4_800)


def test_employee_contribution_zero_for_no_income_or_rate():
    assert kiwisaver_employee_contribution(0, 0.03) == 0
    assert kiwisaver_employee_contribution(80_000, 0) == 0


def test_employer_contribution_defaults_to_three_percent():
    assert kiwisaver_employer_contribution(80_000) == pytest.approx(80_000 * KIWISAVER_DEFAULT_EMPLOYER)


# --- Member Tax Credit ------------------------------------------------------

@pytest.mark.parametrize(
    "contrib, expected",
    [
        (0, 0),
        (-100, 0),
        (500, 250),                                  # below qualifying — half
        (MTC_QUALIFYING_CONTRIB, MTC_ANNUAL_MAX),    # exactly qualifying — full
        (MTC_QUALIFYING_CONTRIB + 1, MTC_ANNUAL_MAX),
        (5_000, MTC_ANNUAL_MAX),                     # capped no matter how much
    ],
)
def test_member_tax_credit_piecewise(contrib, expected):
    assert member_tax_credit(contrib) == pytest.approx(expected)


# --- PIE / RWT --------------------------------------------------------------

@pytest.mark.parametrize("pir", list(PIE_TIERS))
def test_after_pie_return_applies_pir(pir):
    assert after_pie_return(0.075, pir) == pytest.approx(0.075 * (1 - pir))


def test_after_rwt_default_is_thirty_three_percent():
    assert after_rwt_return(0.05) == pytest.approx(0.05 * (1 - 0.33))


def test_after_rwt_custom_rate():
    assert after_rwt_return(0.05, 0.175) == pytest.approx(0.05 * (1 - 0.175))
