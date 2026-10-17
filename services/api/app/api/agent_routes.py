"""Streaming recovery endpoint: one POST, Server-Sent Events until the bounded run ends."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.background import BackgroundTask

from app.agent.interpret import MAX_TEXT, Interpretation, interpret
from app.agent.runner import Budget, run_agent
from app.agent.tools import AgentContext
from app.core.budget import BudgetLimits, InferenceBudget
from app.core.clientip import client_key
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.quota import GlobalQuota, QuotaUnavailableError, Reservation, UpstashQuota
from app.core.ratelimit import ConcurrencyGate, SlidingWindowLimiter
from app.domain.preferences import Preferences
from app.domain.revision import Revision
from app.providers.base import ProviderError
from app.providers.factory import fast_provider, planner_provider
from app.services.workflow import load_problem, verify_revision

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
    return client_key(request)


_quota: GlobalQuota | None = None


def global_quota() -> GlobalQuota | None:
    """The shared quota if configured; raises QuotaUnavailableError if required but unusable."""
    global _quota
    settings = get_settings()
    if _quota is None and settings.upstash_redis_rest_url and settings.upstash_redis_rest_token:
        _quota = UpstashQuota(
            url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token.get_secret_value(),
            daily_budget=settings.ai_global_daily_token_budget,
            lifetime_budget=settings.ai_global_lifetime_token_budget,
        )
    if _quota is None and settings.ai_require_global_quota:
        raise QuotaUnavailableError("A global quota is required but not configured.")
    return _quota


def _reserve_global(tokens: int) -> Reservation | None:
    """Fail closed: any quota problem refuses the request before a model call happens."""
    try:
        quota = global_quota()
        if quota is None:
            return None
        reservation = quota.reserve(tokens)
    except QuotaUnavailableError as exc:
        raise ApiError(
            503,
            "AI_PAUSED",
            "Live AI is unavailable because its spending quota cannot be checked. The playbook search (no AI) still works.",
        ) from exc
    if reservation is None:
        raise ApiError(
            503, "AI_BUDGET_EXHAUSTED", "The live AI budget is used up. The playbook search (no AI) still works."
        )
    return reservation


def _refund_global(reservation: Reservation | None, used: int) -> None:
    if reservation is not None and _quota is not None:
        _quota.refund(reservation, used)


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
    problem = load_problem(scenario, req.revision)  # 400 on malformed or forged plans, before any cost
    try:
        provider = planner_provider(settings)
    except ProviderError as exc:
        raise ApiError(503, "MODEL_UNAVAILABLE", str(exc)) from exc
    preferences = req.preferences.model_copy(update={"source": "structured"}) if req.preferences else None
    try:
        ctx = AgentContext.build(scenario, req.revision, problem, settings.agent_max_evaluations, preferences)
    except (KeyError, ValueError) as exc:
        raise ApiError(400, "INVALID_REVISION", "The revision's plan cannot be analysed.") from exc

    # Order matters: a busy instance must not consume the visitor's daily allowance or budget.
    if not _gate.try_acquire():
        raise ApiError(503, "BUSY", "Recovery engine is busy. Try again shortly.")
    reservation: Reservation | None = None
    try:
        if provider.live:
            _guard(request, "recover")
            reservation = _reserve_global(settings.agent_max_total_tokens)
    except BaseException:
        _gate.release()
        raise
    budget = Budget(
        max_model_calls=settings.agent_max_model_calls,
        max_total_tokens=settings.agent_max_total_tokens,
        timeout_seconds=settings.agent_timeout_seconds,
        max_output_tokens=settings.agent_max_output_tokens,
    )
    mode = "live" if provider.live else "mock"
    released = False

    def release(used: int) -> None:
        nonlocal released
        if not released:
            released = True
            _gate.release()
            _refund_global(reservation, used)

    async def stream() -> AsyncIterator[str]:
        used_tokens = 0
        try:
            async for ev in run_agent(ctx, provider, budget, req.priorities, mode_label=mode):
                if ev.type in ("model_call", "error", "done"):
                    log.info("agent_event type=%s data=%s", ev.type, json.dumps(ev.data, default=str)[:600])
                if ev.type == "model_call" and provider.live:
                    # Counted per call, so a client that disconnects mid-run is still charged to the budget.
                    call_tokens = int(ev.data.get("usage", {}).get("total_tokens", 0))
                    used_tokens += call_tokens
                    inference_budget.record_tokens(call_tokens)
                yield f"event: {ev.type}\ndata: {ev.model_dump_json()}\n\n"
        finally:
            release(used_tokens)

    # If the stream never starts (client gone before the first byte), the background task still releases.
    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        background=BackgroundTask(release, settings.agent_max_total_tokens),
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
    reservation: Reservation | None = None
    if provider.live:
        _guard(request, "interpret")
        reservation = _reserve_global(settings.ai_interpret_token_reservation)
    used = settings.ai_interpret_token_reservation  # assume the worst until the call reports usage
    try:
        result = await interpret(scenario, req.text, provider)
        used = result.total_tokens
        if provider.live:
            inference_budget.record_tokens(result.total_tokens)
        return result
    except ProviderError as exc:
        if provider.live:  # the call may have been billed even though parsing failed
            inference_budget.record_tokens(settings.ai_interpret_token_reservation)
        status = 429 if exc.code == "RATE_LIMITED" else 503
        code = exc.code if exc.code in ("RATE_LIMITED", "CREDIT_EXHAUSTED") else "MODEL_UNAVAILABLE"
        raise ApiError(status, code, str(exc)) from exc
    finally:
        _refund_global(reservation, used)
