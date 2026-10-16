"""Explainable facts about a schedule: slack, binding constraints, impact, cost and diffs."""

from __future__ import annotations

from collections import defaultdict

from app.domain.effective import EffectiveProblem
from app.domain.graph import bfs_waves, longest_path_earliest, topological_order
from app.domain.models import (
    MINUTES_PER_DAY,
    Plan,
    ResourceUnavailableShock,
    Scenario,
    TaskDelayShock,
)
from app.domain.propagate import resource_chain_edges, right_shift
from app.domain.reports import (
    Binding,
    CausalEdge,
    ImpactMetrics,
    ImpactReport,
    ScheduleMetrics,
    ServiceImpact,
    TaskChange,
    TaskImpact,
    TaskStatus,
    TaskTiming,
)
from app.domain.validate import validate_plan


def fmt_clock(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _binding(problem: EffectiveProblem, plan: Plan, task_id: str) -> Binding:
    entries = plan.by_task()
    entry = entries[task_id]
    task = problem.tasks[task_id]
    start = entry.start
    if task_id in problem.pins:
        return Binding(
            kind="pinned", constraint_id=f"patch:{task_id}", text=f"Pinned to {fmt_clock(start)} by the plan."
        )
    for dep in sorted(problem.dependencies, key=lambda d: d.from_id):
        if dep.to_id != task_id or dep.from_id not in entries:
            continue
        pred = problem.tasks[dep.from_id]
        if entries[dep.from_id].start + pred.duration + dep.lag == start:
            return Binding(
                kind="precedence",
                constraint_id=f"prec:{dep.from_id}->{task_id}",
                text=f"Waits for {pred.label}.",
                via=dep.from_id,
            )
    for req in task.requirements:
        rid = entry.assignments.get(req.id)
        if rid is None or rid not in problem.resources:
            continue
        res = problem.resources[rid]
        for other in plan.entries:
            if other.task_id == task_id or rid not in other.assignments.values():
                continue
            other_task = problem.tasks.get(other.task_id)
            if other_task and other_task.duration and other.start + other_task.duration == start:
                return Binding(
                    kind="resource",
                    constraint_id=f"overlap:{rid}",
                    text=f"{res.label} is busy with {other_task.label} until {fmt_clock(start)}.",
                    via=other.task_id,
                )
        if any(w.end == start for w in res.blocked) or (res.available.start == start and start > task.release):
            return Binding(
                kind="availability",
                constraint_id=f"avail:{rid}",
                text=f"{res.label} is unavailable until {fmt_clock(start)}.",
                via=rid,
            )
    if start == task.release:
        return Binding(
            kind="release", constraint_id=f"release:{task_id}", text=f"Cannot start before {fmt_clock(task.release)}."
        )
    return Binding(kind="free", constraint_id=None, text="Has room to start earlier.")


def schedule_timings(problem: EffectiveProblem, plan: Plan) -> tuple[list[TaskTiming], ScheduleMetrics]:
    entries = plan.by_task()
    nodes = [t for t in problem.tasks if t in entries]
    chain = resource_chain_edges(problem, plan)
    edges: list[tuple[str, str, int]] = [
        (d.from_id, d.to_id, d.lag) for d in problem.dependencies if d.from_id in entries and d.to_id in entries
    ]
    edges += [(a, b, 0) for a, b in chain]
    order = topological_order(nodes, [(a, b) for a, b, _ in edges], priority=lambda n: (entries[n].start, n))

    succ: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for a, b, lag in edges:
        succ[a].append((b, lag))
    latest_start: dict[str, int | None] = {}
    for tid in reversed(order):
        task = problem.tasks[tid]
        bounds = [task.deadline] if task.deadline is not None else []
        bounds += [ls - lag for s, lag in succ[tid] if (ls := latest_start[s]) is not None]
        latest_start[tid] = (min(bounds) - task.duration) if bounds else None

    timings: list[TaskTiming] = []
    for tid in order:
        e, task = entries[tid], problem.tasks[tid]
        ls = latest_start[tid]
        timings.append(
            TaskTiming(
                task_id=tid,
                start=e.start,
                end=e.start + task.duration,
                duration=task.duration,
                assignments=dict(e.assignments),
                slack=None if ls is None else ls - e.start,
                binding=_binding(problem, plan, tid),
            )
        )

    scenario = problem.scenario
    deadline_task = scenario.task(scenario.deadline_task_id)
    deadline = deadline_task.deadline if deadline_task.deadline is not None else MINUTES_PER_DAY
    readiness = entries[deadline_task.id].start if deadline_task.id in entries else None
    by_id = {t.task_id: t for t in timings}
    path: list[str] = []
    cursor: str | None = deadline_task.id if readiness is not None else None
    while cursor is not None and cursor not in path:
        path.append(cursor)
        binding = by_id[cursor].binding
        cursor = binding.via if binding.kind in ("precedence", "resource") else None
    path.reverse()
    return timings, ScheduleMetrics(
        readiness=readiness,
        deadline=deadline,
        deadline_delta=None if readiness is None else readiness - deadline,
        driving_path=path,
    )


def precedence_bound(problem: EffectiveProblem) -> tuple[int, list[str]]:
    """Earliest readiness with unlimited resources, plus the chain that drives it."""
    preds: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for d in problem.dependencies:
        preds[d.to_id].append((d.from_id, d.lag))
    order = topological_order(problem.tasks, [(d.from_id, d.to_id) for d in problem.dependencies])
    release = {t: problem.tasks[t].release for t in problem.tasks}
    duration = {t: problem.tasks[t].duration for t in problem.tasks}
    es = longest_path_earliest(order, preds, release, duration)
    target = problem.scenario.deadline_task_id
    chain = [target]
    cursor = target
    while True:
        nxt = next(
            (p for p, lag in sorted(preds[cursor]) if es[p] + duration[p] + lag == es[cursor]),
            None,
        )
        if nxt is None:
            break
        chain.append(nxt)
        cursor = nxt
    chain.reverse()
    return es[target], chain


def shock_sources(problem: EffectiveProblem, reference: Plan) -> list[str]:
    """Tasks whose own constraints are directly changed by a shock."""
    ref = reference.by_task()
    sources: set[str] = set()
    for shock in problem.shocks:
        if isinstance(shock, TaskDelayShock) and shock.task_id in problem.tasks:
            sources.add(shock.task_id)
        elif isinstance(shock, ResourceUnavailableShock):
            for e in reference.entries:
                task = problem.tasks.get(e.task_id)
                if (
                    task
                    and shock.resource_id in e.assignments.values()
                    and shock.window.overlaps(e.start, e.start + task.duration)
                ):
                    sources.add(e.task_id)
    return sorted(s for s in sources if s in ref)


def impact_report(problem: EffectiveProblem, reference: Plan) -> ImpactReport:
    ref = reference.by_task()
    prop = right_shift(problem, reference)
    shifted = prop.plan.by_task()
    sources = shock_sources(problem, reference)
    prec_edges = [(d.from_id, d.to_id) for d in problem.dependencies]
    res_edges = list(prop.resource_edges)
    waves, tree = bfs_waves(sources, prec_edges + res_edges)
    prec_set = set(prec_edges)

    timings, schedule = schedule_timings(problem, prop.plan)
    task_rows: list[TaskImpact] = []
    for tid in problem.tasks:
        if tid not in ref:
            continue
        task = problem.tasks[tid]
        entry = shifted.get(tid)
        delay = None if entry is None else entry.start - ref[tid].start
        if tid in prop.blocked:
            status = TaskStatus.BLOCKED
        elif entry is not None and task.deadline is not None and entry.start + task.duration > task.deadline:
            status = TaskStatus.BREACH
        elif delay:
            status = TaskStatus.DELAYED
        elif tid in waves:
            status = TaskStatus.AT_RISK
        else:
            status = TaskStatus.ON_TRACK
        task_rows.append(
            TaskImpact(
                task_id=tid,
                status=status,
                wave=waves.get(tid),
                reference_start=ref[tid].start,
                start=None if entry is None else entry.start,
                delay=delay,
            )
        )
    task_rows.sort(key=lambda r: (r.reference_start, r.task_id))
    conflicts = validate_plan(problem, reference)
    counts = {s: sum(1 for r in task_rows if r.status == s) for s in TaskStatus}
    return ImpactReport(
        sources=sources,
        tasks=task_rows,
        causal_edges=[
            CausalEdge(from_id=a, to_id=b, kind="precedence" if (a, b) in prec_set else "resource", wave=w)
            for a, b, w in tree
        ],
        timings=timings,
        schedule=schedule,
        metrics=ImpactMetrics(
            at_risk_count=counts[TaskStatus.AT_RISK],
            delayed_count=counts[TaskStatus.DELAYED],
            breach_count=counts[TaskStatus.BREACH],
            blocked_count=counts[TaskStatus.BLOCKED],
            total_delay_minutes=sum(r.delay for r in task_rows if r.delay and r.delay > 0),
            conflicts_if_unchanged=len(conflicts),
        ),
        conflicts_if_unchanged=conflicts,
    )


def intervention_cost_cents(problem: EffectiveProblem, plan: Plan) -> int:
    """Activation fees plus hourly cost of activated standby resources for minutes worked."""
    total = 0
    for rid in sorted(problem.activated):
        res = problem.resources[rid]
        minutes = sum(problem.tasks[e.task_id].duration for e in plan.entries if rid in e.assignments.values())
        total += res.activation_cost_cents + round(res.hourly_cost_cents * minutes / 60)
    return total


def _compress_severity(nominal: int, minimum: int | None, duration: int) -> float:
    """Graded guest impact: cutting 5 of a possible 15 minutes is a third of a full cut."""
    span = nominal - (minimum if minimum is not None else 0)
    return round((nominal - duration) / span, 2) if span > 0 else 1.0


def service_impacts(scenario: Scenario, problem: EffectiveProblem) -> list[ServiceImpact]:
    out: list[ServiceImpact] = []
    for tid, dur in sorted(problem.compressed.items()):
        task = scenario.task(tid)
        note = task.compress_note or f"{task.label} shortened"
        out.append(
            ServiceImpact(
                kind="compress",
                task_id=tid,
                text=f"{note} ({task.duration} → {dur} min)",
                severity=_compress_severity(task.duration, task.min_duration, dur),
            )
        )
    for tid in sorted(problem.deferred):
        task = scenario.task(tid)
        out.append(
            ServiceImpact(
                kind="defer", task_id=tid, text=task.defer_note or f"{task.label} moved after doors open", severity=2
            )
        )
    return out


REASSIGNMENT_WEIGHT = 15
"""Disruption minutes charged per changed assignment: re-briefing a crew costs roughly
a quarter hour of coordination, so one reassignment ~ moving one task by 15 min."""


def plan_changes(
    scenario: Scenario, problem: EffectiveProblem, plan: Plan, reference: Plan
) -> tuple[list[TaskChange], int, int]:
    """Per-task diff against the reference plan, total moved minutes, and reassignment count."""
    ref = reference.by_task()
    new = plan.by_task()
    changes: list[TaskChange] = []
    moved_total = 0
    reassigned_total = 0
    for task in scenario.tasks:
        tid = task.id
        if tid in problem.deferred:
            changes.append(TaskChange(task_id=tid, moved_minutes=None, reassigned=[], deferred=True))
            continue
        if tid not in new or tid not in ref:
            continue
        moved = new[tid].start - ref[tid].start
        reassigned = [
            (req, ref[tid].assignments.get(req), rid)
            for req, rid in sorted(new[tid].assignments.items())
            if ref[tid].assignments.get(req) != rid
        ]
        dur_to = problem.compressed.get(tid)
        if dur_to is None and tid in problem.helpers:
            dur_to = problem.tasks[tid].duration
        if moved or reassigned or dur_to is not None:
            changes.append(
                TaskChange(
                    task_id=tid,
                    moved_minutes=moved,
                    reassigned=reassigned,
                    duration_from=task.duration if dur_to is not None else None,
                    duration_to=dur_to,
                )
            )
        moved_total += abs(moved)
        reassigned_total += len(reassigned)
    return changes, moved_total, reassigned_total
