"""Server-side configuration. Secrets never leave this process."""

from __future__ import annotations

from functools import cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ai_mode: Literal["live", "mock"] = "mock"
    nebius_api_key: SecretStr | None = None
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"
    nebius_model_planner: str = "nvidia/nemotron-3-super-120b-a12b"
    nebius_model_fast: str = "nvidia/nemotron-3-super-120b-a12b"
    nebius_timeout_seconds: float = Field(default=45.0, gt=0, le=120)
    nebius_max_retries: int = Field(default=2, ge=0, le=4)
    nebius_extra_body_json: str = Field(
        default="", description="Extra JSON merged into chat requests, e.g. chat_template_kwargs."
    )

    agent_max_model_calls: int = Field(default=8, ge=1, le=16)
    agent_max_evaluations: int = Field(default=6, ge=1, le=12)
    agent_max_total_tokens: int = Field(default=80_000, ge=1_000, le=400_000)
    agent_timeout_seconds: float = Field(default=90.0, gt=0, le=280)
    agent_max_output_tokens: int = Field(default=4_096, ge=256, le=16_384)

    recover_rate_per_minute: int = Field(default=3, ge=1, le=120)
    recover_max_concurrent: int = Field(default=3, ge=1, le=64)
    solver_rate_per_minute: int = Field(default=40, ge=1, le=1_000)

    # Spend controls (per process, per UTC day). See docs/operations.md for the real worst case.
    ai_kill_switch: bool = Field(default=False, description="Emergency stop: no model calls at all.")
    ai_daily_token_budget: int = Field(default=1_500_000, ge=0, le=50_000_000)
    ai_daily_run_budget: int = Field(default=60, ge=0, le=10_000)
    ai_per_ip_daily_runs: int = Field(default=12, ge=0, le=1_000)

    # Global (cross-instance) quota. When required and unavailable, live AI is refused (fail closed).
    ai_require_global_quota: bool = False
    ai_global_daily_token_budget: int = Field(default=1_500_000, ge=0, le=50_000_000)
    ai_global_lifetime_token_budget: int = Field(default=20_000_000, ge=0, le=500_000_000)
    ai_interpret_token_reservation: int = Field(default=6_000, ge=500, le=50_000)
    upstash_redis_rest_url: str = Field(
        default="", validation_alias=AliasChoices("UPSTASH_REDIS_REST_URL", "KV_REST_API_URL")
    )
    upstash_redis_rest_token: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("UPSTASH_REDIS_REST_TOKEN", "KV_REST_API_TOKEN")
    )

    cors_origins: str = "http://localhost:3000"
    static_dir: str | None = None

    @property
    def live_ready(self) -> bool:
        return (
            self.ai_mode == "live" and self.nebius_api_key is not None and bool(self.nebius_api_key.get_secret_value())
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@cache
def get_settings() -> Settings:
    return Settings()
