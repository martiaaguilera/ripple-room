"""Select the planner provider from settings. Live mode never silently falls back to the mock."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import Settings
from app.providers.base import ChatProvider, ProviderError
from app.providers.mock import MockProvider
from app.providers.nebius import NebiusProvider


def planner_provider(settings: Settings, *, model: str | None = None) -> ChatProvider:
    if settings.ai_mode == "mock":
        return MockProvider(max_evaluations=settings.agent_max_evaluations)
    if not settings.live_ready or settings.nebius_api_key is None:
        raise ProviderError("MODEL_UNAVAILABLE", "Live AI mode is enabled but no Nebius API key is configured.")
    extra: dict[str, Any] = json.loads(settings.nebius_extra_body_json) if settings.nebius_extra_body_json else {}
    return NebiusProvider(
        api_key=settings.nebius_api_key.get_secret_value(),
        base_url=settings.nebius_base_url,
        model=model or settings.nebius_model_planner,
        timeout_seconds=settings.nebius_timeout_seconds,
        max_retries=settings.nebius_max_retries,
        extra_body=extra,
    )


def fast_provider(settings: Settings) -> ChatProvider:
    """Provider for short structured calls (incident interpretation)."""
    return planner_provider(settings, model=settings.nebius_model_fast)
