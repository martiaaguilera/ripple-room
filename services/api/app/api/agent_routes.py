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
from app.core.budget import BudgetLimits, InferenceBudget
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
inference_budget = InferenceBudget(
    BudgetLimits(
        daily_tokens=_settings.ai_daily_token_budget,
        daily_runs=_settings.ai_daily_run_budget,
        per_ip_daily_runs=_settings.ai_per_ip_daily_runs,
    )
)


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
    """Client IP for rate limiting. Prefer headers the platform sets and clients cannot forge:
    on Vercel, x-vercel-forwarded-for / x-real-ip; the first x-forwarded-for entry is client-controlled."""
    for header in ("x-vercel-forwarded-for", "x-real-ip"):
        value = request.headers.get(header, "").split(",")[0].strip()
        if value:
            return value
    forwarded = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if forwarded:
        return forwarded[-1]  # the hop appended by the nearest proxy, not the client's claim
    return request.client.host if request.client else "unknown"


def _guard(request: Request, scope: str) -> None:
    """Kill switch, daily budget and per-client limits, checked before any model call."""
    settings = get_settings()
    if settings.ai_kill_switch:
        raise ApiError(503, "AI_PAUSED", "Live AI is paused by the operator. The playbook search (no AI) still works.")
    client = _client_key(request)
    if not _limiter.allow(f"{scope}:{client}"):
        raise ApiError(429, "RATE_LIMITED", "Too many requests. Try again in a minute.")
    refusal = inference_budget.try_start(client)
    if refusal == "budget":
        raise ApiError(
            503, "AI_BUDGET_EXHAUSTED", "Today's live AI budget is used up. The playbook search (no AI) still works."
        )
    if refusal == "client":
        raise ApiError(429, "RATE_LIMITED", "Daily limit for live AI requests reached from this connection.")


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
    if provider.live:
        _guard(request, "recover")
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
                if ev.type == "model_call" and provider.live:
                    # Counted per call, so a client that disconnects mid-run is still charged to the budget.
                    inference_budget.record_tokens(int(ev.data.get("usage", {}).get("total_tokens", 0)))
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
    if provider.live:
        _guard(request, "interpret")
    try:
        result = await interpret(scenario, req.text, provider)
        if provider.live:
            inference_budget.record_tokens(result.total_tokens)
        return result
    except ProviderError as exc:
        status = 429 if exc.code == "RATE_LIMITED" else 503
        code = exc.code if exc.code in ("RATE_LIMITED", "CREDIT_EXHAUSTED") else "MODEL_UNAVAILABLE"
        raise ApiError(status, code, str(exc)) from exc
