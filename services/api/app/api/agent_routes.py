"""Streaming recovery endpoint: one POST, Server-Sent Events until the bounded run ends."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.agent.interpret import MAX_TEXT, Interpretation, interpret
from app.agent.runner import Budget, run_agent
from app.agent.tools import AgentContext
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.ratelimit import ConcurrencyGate, SlidingWindowLimiter
from app.domain.effective import compile_problem
from app.domain.preferences import Preferences
from app.domain.revision import Revision
from app.providers.base import ProviderError
from app.providers.factory import fast_provider, planner_provider
from app.services.workflow import verify_revision

log = logging.getLogger("ripple.agent")
router = APIRouter(prefix="/api")

_settings = get_settings()
_limiter = SlidingWindowLimiter(_settings.recover_rate_per_minute)
_gate = ConcurrencyGate(_settings.recover_max_concurrent)


class RecoverRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision: Revision
    priorities: str = Field(default="", max_length=500)
    preferences: Preferences | None = None


class InterpretRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    revision: Revision
    text: str = Field(min_length=3, max_length=MAX_TEXT)


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@router.post("/recover")
async def recover(req: RecoverRequest, request: Request) -> StreamingResponse:
    settings = get_settings()
    scenario = verify_revision(req.revision)
    state = req.revision.state
    problem, static = compile_problem(scenario, state.shocks, state.committed)
    if problem is None:
        raise ApiError(
            400, "INVALID_REVISION", "Committed interventions are invalid.", [v.model_dump() for v in static]
        )
    try:
        provider = planner_provider(settings)
    except ProviderError as exc:
        raise ApiError(503, "MODEL_UNAVAILABLE", str(exc)) from exc
    if not _limiter.allow(_client_key(request)):
        raise ApiError(429, "RATE_LIMITED", "Too many recovery runs. Try again in a minute.")
    if not _gate.try_acquire():
        raise ApiError(503, "BUSY", "Recovery engine is busy. Try again shortly.")

    ctx = AgentContext.build(scenario, req.revision, problem, settings.agent_max_evaluations, req.preferences)
    budget = Budget(
        max_model_calls=settings.agent_max_model_calls,
        max_total_tokens=settings.agent_max_total_tokens,
        timeout_seconds=settings.agent_timeout_seconds,
        max_output_tokens=settings.agent_max_output_tokens,
    )
    mode = "live" if provider.live else "mock"

    async def stream() -> AsyncIterator[str]:
        try:
            async for ev in run_agent(ctx, provider, budget, req.priorities, mode_label=mode):
                if ev.type in ("model_call", "error", "done"):
                    log.info(
                        "agent_event type=%s data=%s",
                        ev.type,
                        json.dumps(ev.data, default=str)[:600],
                    )
                yield f"event: {ev.type}\ndata: {ev.model_dump_json()}\n\n"
        finally:
            _gate.release()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/interpret")
async def interpret_incident(req: InterpretRequest, request: Request) -> Interpretation:
    """Turn free text into typed incidents + preferences for the human to confirm. Applies nothing."""
    settings = get_settings()
    scenario = verify_revision(req.revision)
    try:
        provider = fast_provider(settings)
    except ProviderError as exc:
        raise ApiError(503, "MODEL_UNAVAILABLE", str(exc)) from exc
    if not _limiter.allow("interpret:" + _client_key(request)):
        raise ApiError(429, "RATE_LIMITED", "Too many requests. Try again in a minute.")
    try:
        return await interpret(scenario, req.text, provider)
    except ProviderError as exc:
        status = 429 if exc.code == "RATE_LIMITED" else 503
        code = exc.code if exc.code in ("RATE_LIMITED", "CREDIT_EXHAUSTED") else "MODEL_UNAVAILABLE"
        raise ApiError(status, code, str(exc)) from exc
