import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import advisor, health, rates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FinPath AI",
        version="0.2.0",
        description="Holistic NZ financial advisor: cash flow + debts + mortgage + KiwiSaver, "
                    "with a deterministic plan and an LLM-generated narrative.",
    )
    # Allow the explicit list from CORS_ORIGINS plus any localhost / RFC1918 LAN
    # origin (any port) so the dev server is usable from other devices on the
    # same network without further config.
    _lan_origin_regex = (
        r"^https?://("
        r"localhost|127\.0\.0\.1|"
        r"10(\.\d{1,3}){3}|"
        r"192\.168(\.\d{1,3}){2}|"
        r"172\.(1[6-9]|2\d|3[01])(\.\d{1,3}){2}"
        r")(:\d+)?$"
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=_lan_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(rates.router, prefix="/api")
    app.include_router(advisor.router, prefix="/api")
    return app


app = create_app()
