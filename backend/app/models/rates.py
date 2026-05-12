from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MortgageRates(BaseModel):
    """Annual nominal rates expressed as decimals (0.0625 = 6.25%)."""
    fixed_1y: float = Field(..., ge=0)
    fixed_2y: float = Field(..., ge=0)
    fixed_3y: float = Field(..., ge=0)
    fixed_5y: float = Field(..., ge=0)
    floating: float = Field(..., ge=0)


class SavingsRates(BaseModel):
    """Annual nominal rates expressed as decimals."""
    high_yield_savings: float = Field(..., ge=0)
    term_deposit_6m: float = Field(..., ge=0)
    term_deposit_12m: float = Field(..., ge=0)
    term_deposit_24m: float = Field(..., ge=0)


class MarketSnapshot(BaseModel):
    """Everything the UI needs to render the rates banner in one round-trip."""
    mortgage: MortgageRates
    savings: SavingsRates
    index_fund_avg_return: float = Field(..., description="Long-run average annual return for a diversified index fund")
    inflation: float = Field(..., description="Current annual CPI rate")
    central_bank_rate: float = Field(..., description="OCR (Official Cash Rate) for NZ-flavored framing")
    source: Literal["mock", "live", "live-fallback"]
    fetched_at: datetime
