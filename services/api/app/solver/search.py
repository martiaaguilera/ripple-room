"""Deterministic recovery search over the scenario's permitted intervention menu.

Used as (a) the clearly labelled offline fallback when the model is unavailable
and (b) the "solver only, no AI" baseline in the evaluation harness. It
enumerates combinations of menu items, verifies each with ``evaluate_patch``
and keeps subset-minimal verified patches.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from pydantic import BaseModel, ConfigDict

from app.domain.models import (
    ActivateResource,
    CompressTask,
    DeferTask,
    Intervention,
    Patch,
    Plan,
    Scenario,
    Shock,
)
from app.domain.reports import Evaluation, EvaluationStatus
from app.solver.cpsat import SolveConfig
from app.solver.evaluate import evaluate_patch

MAX_MENU_COMBINATION = 4


class MenuItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    label: str
    kind: str
    actions: tuple[Intervention, ...]
    cost_hint: str
    tradeoff: str


def _defer_closure(scenario: Scenario, task_id: str) -> list[str] | None:
    """Tasks that must be deferred together with ``task_id``; None if a required task would break."""
    succ: dict[str, list[str]] = defaultdict(list)
    for d in scenario.dependencies:
        if not d.waived_if_deferred:
            succ[d.from_id].append(d.to_id)
    seen: list[str] = []
    stack = [task_id]
    while stack:
        tid = stack.pop()
        if tid in seen:
            continue
        if not scenario.task(tid).optional:
            return None
        seen.append(tid)
        stack.extend(succ[tid])
    return sorted(seen)


def intervention_menu(scenario: Scenario) -> list[MenuItem]:
    items: list[MenuItem] = []
    for res in scenario.resources:
        if res.standby:
            fee = res.activation_cost_cents / 100
            rate = f" + €{res.hourly_cost_cents / 100:.0f}/h" if res.hourly_cost_cents else ""
            items.append(
                MenuItem(
                    id=f"activate:{res.id}",
                    label=f"Bring in {res.label.lower()}",
                    kind="activate_resource",
                    actions=(ActivateResource(resource_id=res.id),),
                    cost_hint=f"€{fee:.0f}{rate}",
                    tradeoff=res.note or "Adds capacity at a cost.",
                )
            )
    for task in scenario.tasks:
        if task.min_duration is not None:
            items.append(
                MenuItem(
                    id=f"compress:{task.id}",
                    label=f"Shorten {task.label.lower()} to {task.min_duration} min",
                    kind="compress_task",
                    actions=(CompressTask(task_id=task.id, duration=task.min_duration),),
                    cost_hint="€0",
                    tradeoff=task.compress_note or "Quality trade-off.",
                )
            )
    for task in scenario.tasks:
        if task.optional:
            closure = _defer_closure(scenario, task.id)
            if closure is None:
                continue
            labels = ", ".join(scenario.task(t).label.lower() for t in closure)
            items.append(
                MenuItem(
                    id=f"defer:{'+'.join(closure)}",
                    label=f"Defer {labels} until after doors",
                    kind="defer_task",
                    actions=tuple(DeferTask(task_id=t) for t in closure),
                    cost_hint="€0",
                    tradeoff=task.defer_note or "Guest-facing scope cut.",
                )
            )
    unique: dict[str, MenuItem] = {}
    for item in items:
        unique.setdefault(item.id, item)
    return list(unique.values())


@dataclass(frozen=True)
class SearchResult:
    verified: list[tuple[MenuItem, ...]]
    evaluations: list[Evaluation]
    combinations_tried: int
    solver_ms: int


def rank_key(ev: Evaluation) -> tuple[int, int, int]:
    """Documented lexicographic ranking among verified plans:
    guest-facing service impact, then money, then disruption to the original plan."""
    return (sum(s.severity for s in ev.service_impacts), ev.cost_cents, ev.disruption_minutes)


def search_recoveries(
    scenario: Scenario,
    shocks: Sequence[Shock],
    committed: Patch,
    reference: Plan,
    *,
    max_size: int = MAX_MENU_COMBINATION,
    config: SolveConfig | None = None,
) -> SearchResult:
    menu = intervention_menu(scenario)
    verified: list[tuple[MenuItem, ...]] = []
    evaluations: list[Evaluation] = []
    tried = 0
    solver_ms = 0
    for size in range(0, max_size + 1):
        for combo in combinations(menu, size):
            touched = [a.task_id for item in combo for a in item.actions if isinstance(a, DeferTask)]
            if len(touched) != len(set(touched)):
                continue
            ids = {item.id for item in combo}
            if any({v.id for v in prior} <= ids for prior in verified):
                continue  # a strict subset already works; keep only minimal patches
            tried += 1
            patch = Patch(actions=tuple(a for item in combo for a in item.actions))
            ev = evaluate_patch(scenario, shocks, committed, patch, reference, config=config, explain_infeasible=False)
            solver_ms += ev.solver.wall_ms
            if ev.status == EvaluationStatus.VERIFIED:
                verified.append(combo)
                evaluations.append(ev)
    order = sorted(range(len(evaluations)), key=lambda i: rank_key(evaluations[i]))
    return SearchResult(
        verified=[verified[i] for i in order],
        evaluations=[evaluations[i] for i in order],
        combinations_tried=tried,
        solver_ms=solver_ms,
    )
