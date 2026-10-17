"""Bounded Perceive → Diagnose → Plan → Verify → Revise → Present loop.

Emits a typed event for everything that actually happens (model calls, tool
calls, verifier verdicts), so the UI can show real progress and never a fake
"thinking" animation. Hard caps: model calls, verifier evaluations, total
tokens and wall-clock time.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.agent.prompts import FINAL_STEP, NUDGE, PROMPT_VERSION, SYSTEM_PROMPT, user_prompt
from app.agent.tools import TOOL_SUBMIT_OPTIONS, AgentContext, execute_tool, preferences_view, tool_specs
from app.domain.preferences import PreferenceReport
from app.domain.ranking import rank_options
from app.domain.reports import Evaluation, EvaluationStatus
from app.providers.base import ChatProvider, Message, ProviderError

EventType = Literal[
    "run_started", "phase", "model_call", "tool_call", "tool_result", "candidate", "options", "error", "done"
]

_EXCERPT = 240  # model text echoed to clients is kept short (abuse surface)
# On the last allowed call the model must choose from what it has verified, so every run ends with its own pick.
_FINALIZE: dict[str, Any] = {"type": "function", "function": {"name": TOOL_SUBMIT_OPTIONS}}


class AgentEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    seq: int
    type: EventType
    at_ms: int
    data: dict[str, Any]


class AgentOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_id: str
    title: str
    why: str
    evaluation: Evaluation
    rank: int  # deterministic rank under the confirmed preferences (1 = best)
    model_rank: int | None  # position the model gave it in submit_options, if any
    report: PreferenceReport
    touched: tuple[str, ...]
    origin: str  # "model" (proposed by the model), "playbook" (deterministic search) or "no_change"


@dataclass(frozen=True)
class Budget:
    max_model_calls: int
    max_total_tokens: int
    timeout_seconds: float
    max_output_tokens: int


def _excerpt(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    return text if len(text) <= _EXCERPT else text[:_EXCERPT].rstrip() + "…"


async def run_agent(
    ctx: AgentContext,
    provider: ChatProvider,
    budget: Budget,
    priorities: str,
    *,
    mode_label: str,
) -> AsyncIterator[AgentEvent]:
    run_id = "run_" + uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    seq = 0

    def event(kind: EventType, **data: Any) -> AgentEvent:
        nonlocal seq
        seq += 1
        return AgentEvent(seq=seq, type=kind, at_ms=round((time.perf_counter() - t0) * 1000), data=data)

    yield event(
        "run_started",
        run_id=run_id,
        base_revision_id=ctx.revision.id,
        provider=provider.name,
        model=provider.model,
        live=provider.live,
        mode=mode_label,
        prompt_version=PROMPT_VERSION,
        budget={
            "model_calls": budget.max_model_calls,
            "evaluations": ctx.max_evaluations,
            "tokens": budget.max_total_tokens,
            "seconds": budget.timeout_seconds,
        },
    )

    messages: list[Message] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt(priorities, preferences_view(ctx.preferences))},
    ]
    tools = tool_specs()
    tokens_used = 0
    calls = 0
    nudged = False
    last_phase: str | None = None
    stop_reason = "budget_exhausted"

    while calls < budget.max_model_calls:
        elapsed = time.perf_counter() - t0
        remaining = budget.timeout_seconds - elapsed
        if remaining <= 1:
            stop_reason = "time_budget"
            break
        if tokens_used >= budget.max_total_tokens:
            stop_reason = "token_budget"
            break
        calls += 1
        if calls == budget.max_model_calls and ctx.candidates:
            messages.append({"role": "user", "content": FINAL_STEP})
        try:
            result = await asyncio.wait_for(
                provider.complete(
                    messages,
                    tools=tools,
                    max_tokens=budget.max_output_tokens,
                    tool_choice=_FINALIZE if calls == budget.max_model_calls and ctx.candidates else "auto",
                ),
                timeout=remaining,
            )
        except TimeoutError:
            yield event("error", code="MODEL_TIMEOUT", message="Model call exceeded the run time budget.")
            stop_reason = "time_budget"
            break
        except ProviderError as exc:
            yield event("error", code=exc.code, message=str(exc), status=exc.status)
            stop_reason = "provider_error"
            break
        tokens_used += result.usage.total_tokens
        yield event(
            "model_call",
            n=calls,
            model=result.model,
            latency_ms=result.latency_ms,
            request_id=result.request_id,
            finish_reason=result.finish_reason,
            usage={
                "prompt_tokens": result.usage.prompt_tokens,
                "completion_tokens": result.usage.completion_tokens,
                "total_tokens": result.usage.total_tokens,
            },
            tool_calls=[c.name for c in result.tool_calls],
            # Raw model reasoning is never forwarded or stored; only whether the model returned any.
            reasoning_returned=bool(result.reasoning),
            content_excerpt=_excerpt(result.content),
        )
        messages.append(result.raw_message or {"role": "assistant", "content": result.content or ""})

        if not result.tool_calls:
            if nudged:
                stop_reason = "no_tool_calls"
                break
            nudged = True
            messages.append({"role": "user", "content": NUDGE})
            continue

        terminal = False
        for call in result.tool_calls:
            yield event("tool_call", id=call.id, name=call.name, arguments=_excerpt(call.arguments))
            outcome = await asyncio.to_thread(execute_tool, ctx, call.name, call.arguments)
            if outcome.phase != last_phase:
                last_phase = outcome.phase
                yield event("phase", name=outcome.phase)
            yield event("tool_result", id=call.id, name=call.name, ok=outcome.ok, summary=outcome.summary)
            if outcome.candidate is not None:
                yield event(
                    "candidate",
                    candidate_id=outcome.candidate.id,
                    rationale=outcome.candidate.rationale,
                    evaluation=outcome.candidate.evaluation.model_dump(mode="json"),
                )
            messages.append(
                {"role": "tool", "tool_call_id": call.id, "content": json.dumps(outcome.content, separators=(",", ":"))}
            )
            terminal = terminal or outcome.terminal
        if terminal:
            stop_reason = "submitted"
            break

    options, finalized = _final_options(ctx)
    yield event(
        "options",
        finalized_by_model=finalized,
        summary=ctx.submitted.summary if ctx.submitted else None,
        options=[o.model_dump(mode="json") for o in options],
    )
    yield event(
        "done",
        run_id=run_id,
        stop_reason=stop_reason,
        model_calls=calls,
        evaluations=ctx.evaluations_used,
        tokens=tokens_used,
        elapsed_ms=round((time.perf_counter() - t0) * 1000),
    )


def _final_options(ctx: AgentContext) -> tuple[list[AgentOption], bool]:
    """Rank the model's verified options deterministically; keep the model's own order for audit.

    If the model did not finish, its verified candidates are surfaced (top 3 by rank) and the
    event says so via ``finalized_by_model=False``.
    """
    finalized = ctx.submitted is not None
    chosen: dict[str, tuple[int | None, str, str]]
    if ctx.submitted is not None:
        chosen = {o.candidate_id: (i + 1, o.title, o.why) for i, o in enumerate(ctx.submitted.options)}
    else:
        chosen = {
            c.id: (None, f"Verified candidate {c.id}", c.rationale)
            for c in ctx.candidates.values()
            if c.evaluation.status == EvaluationStatus.VERIFIED and c.origin == "model"
        }
    # Server-verified alternatives are always offered: "keep the current plan" (c0, measured miss in c14)
    # and the playbook options (p1..pn), so the system never ranks below the deterministic playbook.
    for cid, cand in ctx.candidates.items():
        if cand.origin != "model" and cid not in chosen:
            title = "Keep the current plan" if cand.origin == "no_change" else cand.rationale
            chosen[cid] = (None, title, cand.rationale)
    ranked = rank_options(
        [(cid, ctx.candidates[cid].evaluation) for cid in chosen],
        ctx.preferences,
        ctx.problem,
        ctx.revision.state.plan,
    )
    limit = None if finalized else 5
    return [
        AgentOption(
            candidate_id=r.id,
            title=chosen[r.id][1],
            why=chosen[r.id][2],
            evaluation=r.evaluation,
            rank=r.rank,
            model_rank=chosen[r.id][0],
            report=r.report,
            touched=r.touched,
            origin=ctx.candidates[r.id].origin,
        )
        for r in ranked[:limit]
    ], finalized
