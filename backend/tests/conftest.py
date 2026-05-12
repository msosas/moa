import pytest

from app.config import get_settings
from app.services import advisor_llm as advisor_llm_service
from app.services import rates as rates_service


@pytest.fixture(autouse=True)
def _reset_singletons():
    get_settings.cache_clear()
    rates_service.reset_provider()
    advisor_llm_service.reset_advisor_llm()
    yield
    get_settings.cache_clear()
    rates_service.reset_provider()
    advisor_llm_service.reset_advisor_llm()
