"""Greedy baseline: the 'experienced coordinator with a playbook' heuristic.

Preference-blind by design. Starting from no intervention, repeatedly add the
single playbook item that brings the best achievable readiness closest to the
deadline (ties: cheaper, then playbook order), until the verifier accepts the
patch or no item improves the relaxed readiness. Deterministic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.models import AddHelper, CompressTask, DeferTask, Patch, Plan, Scenario, Shock
from app.domain.reports import Evaluation, EvaluationStatus
from app.solver.evaluate import evaluate_patch
from app.solver.search import MenuItem, intervention_menu

MAX_STEPS = 4


@dataclass(frozen=True)
class GreedyResult:
    evaluation: Evaluation | None
    steps: list[str]
    evaluations: int
    solver_ms: int


def _readiness(ev: Evaluation) -> int:
    if ev.status == EvaluationStatus.VERIFIED and ev.schedule and ev.schedule.readiness is not None:
        return ev.schedule.readiness
    if ev.infeasibility and ev.infeasibility.best_readiness is not None:
        return ev.infeasibility.best_readiness
    return 10**6


def _tasks(item: MenuItem) -> set[str]:
    return {a.task_id for a in item.actions if isinstance(a, DeferTask | CompressTask | AddHelper)}


def greedy_recovery(scenario: Scenario, shocks: Sequence[Shock], committed: Patch, reference: Plan) -> GreedyResult:
    chosen: list[MenuItem] = []
    evaluations = 0
    solver_ms = 0
    current = evaluate_patch(scenario, shocks, committed, Patch(), reference)
    evaluations += 1
    solver_ms += current.solver.wall_ms
    if current.status == EvaluationStatus.VERIFIED:
        return GreedyResult(current, [], evaluations, solver_ms)
    menu = intervention_menu(scenario)
    best_now = _readiness(current)
    for _ in range(MAX_STEPS):
        best: tuple[int, int, int, MenuItem, Evaluation] | None = None
        used_tasks = set().union(*(_tasks(i) for i in chosen)) if chosen else set()
        for order, item in enumerate(menu):
            if item in chosen or _tasks(item) & used_tasks:
                continue
            patch = Patch(actions=tuple(a for i in (*chosen, item) for a in i.actions))
            ev = evaluate_patch(scenario, shocks, committed, patch, reference)
            evaluations += 1
            solver_ms += ev.solver.wall_ms
            if ev.status == EvaluationStatus.REJECTED:
                continue
            key = (_readiness(ev), ev.cost_cents, order)
            if best is None or key < best[:3]:
                best = (*key, item, ev)
        if best is None or best[0] >= best_now:
            return GreedyResult(None, [i.id for i in chosen], evaluations, solver_ms)
        chosen.append(best[3])
        best_now = best[0]
        if best[4].status == EvaluationStatus.VERIFIED:
            return GreedyResult(best[4], [i.id for i in chosen], evaluations, solver_ms)
    return GreedyResult(None, [i.id for i in chosen], evaluations, solver_ms)
