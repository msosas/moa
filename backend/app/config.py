from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    rate_provider_type: Literal["mock", "live"] = "mock"
    api_ninjas_key: str | None = None
    rates_cache_ttl_seconds: int = 3600
    cors_origins: str = "http://localhost:5173"

    # --- Advisor LLM narrative -------------------------------------------------
    anthropic_api_key: str | None = None
    ollama_base_url: str | None = "http://host.docker.internal:11434"
    advisor_model: str = "claude-sonnet-4-6"
    advisor_narrative_enabled: bool = True
    advisor_max_output_tokens: int = 800

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _gate_narrative_on_provider(self) -> "Settings":
        # Narrative is enabled if either provider is configured. If neither is,
        # the service silently serves the templated fallback.
        if not self.anthropic_api_key and not self.ollama_base_url:
            self.advisor_narrative_enabled = False
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
