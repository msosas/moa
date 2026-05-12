from fastapi import APIRouter, Depends

from app.models.rates import MarketSnapshot
from app.services.rates import RateProvider, get_provider

router = APIRouter()


def _provider() -> RateProvider:
    return get_provider()


@router.get("/rates", response_model=MarketSnapshot)
async def rates(provider: RateProvider = Depends(_provider)) -> MarketSnapshot:
    return await provider.get_market_snapshot()
