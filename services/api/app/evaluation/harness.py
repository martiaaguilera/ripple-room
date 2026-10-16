"""Evaluation harness: agent vs playbook search vs greedy vs extended oracle.

Fairness rules:
* identical scenario, shocks, committed state and structured preferences for every method;
* every option any method returns is re-checked by the independent validator;
* every method's best option is chosen by the same deterministic preference ranking;
* the extended oracle enumerates the agent's reachable action space (helpers and partial
  compressions included) and is an upper bound, not a competitor.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.agent.runner import Budget, run_agent
from app.agent.tools import AgentContext
from app.domain.effective import compile_problem
from app.domain.models import AddHelper, AssignResource, CompressTask, Patch, PinStart, Scenario
from app.domain.preferences import Preferences
from app.domain.ranking import RankedOption, rank_options
from app.domain.reports import Evaluation
from app.domain.revision import Revision, baseline_revision
from app.domain.validate import validate_plan
from app.evaluation.cases import Case
from app.providers.base import ChatProvider
from app.services.workflow import add_shock
from app.solver.greedy import greedy_recovery
from app.solver.search import extended_menu, search_recoveries

ORACLE_MAX_SIZE = 3


class BestOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    actions: list[dict[str, Any]]
    cost_cents: int
    readiness: int | None
    margin: int | None
    breaches: list[str]
    penalty: float


class MethodResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: str
    found: bool
    options: int
    best: BestOption | None
    invalid_options: int
    elapsed_ms: int
    solver_evaluations: int
    model_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    rejected_candidates: int = 0
    beyond_playbook_actions: int = 0
    finalized_by_model: bool | None = None
    top_pick_agrees: bool | None = None
    stop_reason: str | None = None
    error: str | None = None


class CaseResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    title: str
    profile: str
    methods: dict[str, MethodResult]


def case_revision(scenario: Scenario, case: Case) -> Revision:
    revision = baseline_revision(scenario)
    for shock in case.shocks:
        revision = add_shock(revision, shock).revision
    return revision


def _invalid(scenario: Scenario, revision: Revision, evaluations: Sequence[Evaluation]) -> int:
    bad = 0
    state = revision.state
    for ev in evaluations:
        merged = Patch(
            actions=state.committed.actions + tuple(a for a in ev.patch.actions if a not in state.committed.actions)
        )
        problem, _ = compile_problem(scenario, state.shocks, merged)
        if problem is None or ev.plan is None or validate_plan(problem, ev.plan):
            bad += 1
    return bad


def _best(ranked: list[RankedOption]) -> BestOption | None:
    if not ranked:
        return None
    top = ranked[0]
    ev = top.evaluation
    delta = ev.schedule.deadline_delta if ev.schedule else None
    return BestOption(
        actions=[a.model_dump() for a in ev.patch.actions],
        cost_cents=ev.cost_cents,
        readiness=ev.schedule.readiness if ev.schedule else None,
        margin=None if delta is None else -delta,
        breaches=[b.text for b in top.report.breaches],
        penalty=top.report.total_points,
    )


def _ranked(
    scenario: Scenario, revision: Revision, prefs: Preferences, items: list[tuple[str, Evaluation]]
) -> list[RankedOption]:
    state = revision.state
    problem, _ = compile_problem(scenario, state.shocks, state.committed)
    assert problem is not None  # noqa: S101 - case shocks are fixture-validated
    return rank_options(items, prefs, problem, state.plan)


def run_search(scenario: Scenario, case: Case, *, oracle: bool) -> MethodResult:
    revision = case_revision(scenario, case)
    state = revision.state
    t0 = time.perf_counter()
    if oracle:
        result = search_recoveries(
            scenario, state.shocks, state.committed, state.plan, max_size=ORACLE_MAX_SIZE, menu=extended_menu(scenario)
        )
    else:
        result = search_recoveries(scenario, state.shocks, state.committed, state.plan)
    elapsed = round((time.perf_counter() - t0) * 1000)
    items = [(f"s{i}", ev) for i, ev in enumerate(result.evaluations)]
    ranked = _ranked(scenario, revision, case.profile.preferences, items)
    return MethodResult(
        method="oracle" if oracle else "playbook_search",
        found=bool(ranked),
        options=len(ranked),
        best=_best(ranked),
        invalid_options=_invalid(scenario, revision, result.evaluations),
        elapsed_ms=elapsed,
        solver_evaluations=result.combinations_tried,
    )


def run_greedy(scenario: Scenario, case: Case) -> MethodResult:
    revision = case_revision(scenario, case)
    state = revision.state
    t0 = time.perf_counter()
    result = greedy_recovery(scenario, state.shocks, state.committed, state.plan)
    elapsed = round((time.perf_counter() - t0) * 1000)
    evs = [result.evaluation] if result.evaluation else []
    ranked = _ranked(scenario, revision, case.profile.preferences, [("g", ev) for ev in evs])
    return MethodResult(
        method="greedy",
        found=bool(ranked),
        options=len(ranked),
        best=_best(ranked),
        invalid_options=_invalid(scenario, revision, evs),
        elapsed_ms=elapsed,
        solver_evaluations=result.evaluations,
    )


def _beyond_playbook(patch: Patch, scenario: Scenario) -> int:
    count = 0
    for a in patch.actions:
        if isinstance(a, AddHelper | PinStart | AssignResource) or (
            isinstance(a, CompressTask) and a.duration != scenario.task(a.task_id).min_duration
        ):
            count += 1
    return count


async def run_agent_case(
    scenario: Scenario,
    case: Case,
    provider: ChatProvider,
    budget: Budget,
    max_evaluations: int,
    pricing: dict[str, tuple[float, float]],
) -> MethodResult:
    revision = case_revision(scenario, case)
    state = revision.state
    problem, _ = compile_problem(scenario, state.shocks, state.committed)
    assert problem is not None  # noqa: S101
    ctx = AgentContext.build(scenario, revision, problem, max_evaluations, case.profile.preferences)
    t0 = time.perf_counter()
    prompt = completion = calls = 0
    cost = 0.0
    error: str | None = None
    options_data: dict[str, Any] = {}
    stop: str | None = None
    async for ev in run_agent(ctx, provider, budget, case.profile.text, mode_label="live" if provider.live else "mock"):
        if ev.type == "model_call":
            calls += 1
            usage = ev.data["usage"]
            prompt += int(usage["prompt_tokens"])
            completion += int(usage["completion_tokens"])
            price_in, price_out = pricing.get(str(ev.data["model"]), pricing.get(provider.model, (0.0, 0.0)))
            cost += int(usage["prompt_tokens"]) * price_in + int(usage["completion_tokens"]) * price_out
        elif ev.type == "error":
            error = f"{ev.data.get('code')}: {ev.data.get('message')}"
        elif ev.type == "options":
            options_data = ev.data
        elif ev.type == "done":
            stop = str(ev.data.get("stop_reason"))
    elapsed = round((time.perf_counter() - t0) * 1000)
    options = options_data.get("options", [])
    evaluations = [Evaluation.model_validate(o["evaluation"]) for o in options]
    ranked = _ranked(
        scenario,
        revision,
        case.profile.preferences,
        [(o["candidate_id"], e) for o, e in zip(options, evaluations, strict=True)],
    )
    model_first = next((o["candidate_id"] for o in options if o.get("model_rank") == 1), None)
    all_candidates = list(ctx.candidates.values())
    return MethodResult(
        method="agent",
        found=bool(ranked),
        options=len(ranked),
        best=_best(ranked),
        invalid_options=_invalid(scenario, revision, evaluations),
        elapsed_ms=elapsed,
        solver_evaluations=ctx.evaluations_used,
        model_calls=calls,
        prompt_tokens=prompt,
        completion_tokens=completion,
        cost_usd=round(cost, 6),
        rejected_candidates=sum(1 for c in all_candidates if c.evaluation.status.value != "verified"),
        beyond_playbook_actions=sum(_beyond_playbook(c.evaluation.patch, scenario) for c in all_candidates),
        finalized_by_model=options_data.get("finalized_by_model"),
        top_pick_agrees=None if model_first is None or not ranked else model_first == ranked[0].id,
        stop_reason=stop,
        error=error,
    )
