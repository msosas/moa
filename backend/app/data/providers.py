"""Curated NZ provider catalog.

Editorial picks for a beginner — not exhaustive, not financial advice. Each
entry carries a short ``why`` so the user understands the trade-off rather
than just seeing a name.

Most New Zealanders bank with one of ANZ / ASB / BNZ / Kiwibank / Westpac and
won't move their main banking just to chase a savings or term-deposit rate.
That's a reasonable default — so the first entry in each list is "your main
bank" framing the simplest path. The specialist-bank options follow as
*alternatives* for users who care about the rate gap and are willing to open
a second account.

Indicative rates are computed as *spreads* relative to the day's market data,
so the displayed numbers track the rates panel. Real bank rates change weekly
and won't match exactly — confirm before committing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderTemplate:
    name: str
    why: str
    url: str | None
    rate_spread_bps: int = 0  # basis points above (positive) or below (negative) the market reference


# --- High-yield / on-call savings ---------------------------------------------
HIGH_YIELD_SAVINGS: list[ProviderTemplate] = [
    ProviderTemplate(
        name="Your main bank's bonus saver",
        why="Easiest path. ANZ Serious Saver / ASB Savings Plus / BNZ Rapid Save / Kiwibank Notice Saver / Westpac Bonus Saver — most pay a bonus rate when you don't withdraw in a month. Slightly lower rate than specialists, but no new account to set up.",
        url=None,
        rate_spread_bps=-30,
    ),
    ProviderTemplate(
        name="Heartland Direct Call",
        why="Consistently top of the on-call rate tables, no notice period, no fees. Worth the ~30bps premium if your buffer is large enough that the gap covers the friction.",
        url="https://www.heartland.co.nz/savings/direct-call-account",
        rate_spread_bps=+30,
    ),
    ProviderTemplate(
        name="Rabobank PremiumSaver",
        why="Bonus rate when you grow your balance each month — great for forced-savings habits. Dutch co-operative bank, AA-rated.",
        url="https://www.rabobank.co.nz/savings/premiumsaver",
        rate_spread_bps=+20,
    ),
]

# --- 12-month term deposits ---------------------------------------------------
# TDs are different from savings: they're easy to open at *any* bank fully
# online. Many people shop around for TDs even if they keep their main banking
# elsewhere — so the friction here is genuinely lower than for an everyday
# bonus-saver account.
TERM_DEPOSIT_12M: list[ProviderTemplate] = [
    ProviderTemplate(
        name="Your main bank (ANZ / ASB / BNZ / Kiwibank / Westpac)",
        why="Big banks usually sit ~20bps below the specialist rate. Easiest if you already bank there — no new AML/IRD setup. Compare current published rates at interest.co.nz before committing.",
        url="https://www.interest.co.nz/saving/term-deposit-rates",
        rate_spread_bps=-20,
    ),
    ProviderTemplate(
        name="Heartland Bank 12-mo TD",
        why="Reliably one of the highest 12-month rates among NZ-licensed banks. Easy to open online; your main banking can stay where it is.",
        url="https://www.heartland.co.nz/term-deposits",
        rate_spread_bps=+15,
    ),
    ProviderTemplate(
        name="Rabobank 12-mo TD",
        why="Consistently competitive; AA-rated. Good middle-ground if you want a non-big-four name without going specialist.",
        url="https://www.rabobank.co.nz/term-deposits",
        rate_spread_bps=+5,
    ),
]

# --- Diversified index funds --------------------------------------------------
# Index funds aren't bank products — they're investment platforms. You use
# them *alongside* whatever bank you already have, not instead of one.
INDEX_FUND: list[ProviderTemplate] = [
    ProviderTemplate(
        name="Kernel Global 100",
        why="Low-fee (~0.25%) NZ-domiciled fund tracking the world's 100 biggest companies. PIE-taxed, so no FIF headaches at tax time.",
        url="https://kernelwealth.co.nz/funds/global-100",
    ),
    ProviderTemplate(
        name="Smartshares Total World (TWF)",
        why="NZX-listed ETF tracking the full global stock market — broadest diversification in one ticker. Buy through Sharesies / Hatch / direct broker.",
        url="https://smartshares.co.nz/our-funds/twf",
    ),
    ProviderTemplate(
        name="Simplicity Growth",
        why="Low-fee (~0.30%) NZ provider; auto-rebalanced multi-asset fund. Set-and-forget for beginners — the easiest of the three.",
        url="https://simplicity.kiwi/investment-funds/growth-fund/",
    ),
    ProviderTemplate(
        name="InvestNow / Sharesies",
        why="Platforms (not funds) that let you buy the funds above without paying the bank's wrapper fees. Use one of these alongside your main bank.",
        url="https://www.investnow.co.nz/",
    ),
]


def materialise(templates: list[ProviderTemplate], reference_rate: float) -> list[dict]:
    """Resolve ``rate_spread_bps`` against a reference rate into a concrete indicative rate."""
    return [
        {
            "name": t.name,
            "why": t.why,
            "url": t.url,
            "indicative_rate": max(0.0, reference_rate + t.rate_spread_bps / 10_000),
        }
        for t in templates
    ]
