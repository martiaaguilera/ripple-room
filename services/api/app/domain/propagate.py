"""Realized impact of a disruption when nobody intervenes ("right-shift").

The reference plan keeps its resource assignments and the order in which each
resource works through its tasks; tasks may only move later. This mirrors what
happens on the floor when a crew simply waits for upstream work.
"""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass

from app.domain.effective import EffectiveProblem
from app.domain.graph import Edge, topological_order
from app.domain.models import Plan, PlanEntry


@dataclass(frozen=True)
class Propagation:
    plan: Plan
    blocked: frozenset[str]
    resource_edges: tuple[Edge, ...]


def resource_chain_edges(problem: EffectiveProblem, plan: Plan) -> list[Edge]:
    """Consecutive tasks on the same resource, in plan order."""
    by_resource: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for entry in plan.entries:
        task = problem.tasks.get(entry.task_id)
        if task is None or task.duration == 0:
            continue
        for rid in entry.assignments.values():
            by_resource[rid].append((entry.start, entry.task_id))
    edges: list[Edge] = []
    for seq in by_resource.values():
        seq.sort()
        edges.extend((a, b) for (_, a), (_, b) in itertools.pairwise(seq))
    return sorted(set(edges))


def right_shift(problem: EffectiveProblem, reference: Plan) -> Propagation:
    ref = reference.by_task()
    nodes = [t for t in problem.tasks if t in ref]
    chain = resource_chain_edges(problem, reference)
    prec = [(d.from_id, d.to_id) for d in problem.dependencies]
    order = topological_order(nodes, prec + chain, priority=lambda n: (ref[n].start, n))

    preds: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for d in problem.dependencies:
        preds[d.to_id].append((d.from_id, d.lag))
    for a, b in chain:
        preds[b].append((a, 0))

    starts: dict[str, int] = {}
    blocked: set[str] = set()
    for tid in order:
        task = problem.tasks[tid]
        entry = ref[tid]
        if any(p in blocked for p, _ in preds[tid]):
            blocked.add(tid)
            continue
        start = max(entry.start, task.release)
        for p, lag in preds[tid]:
            start = max(start, starts[p] + problem.tasks[p].duration + lag)
        assigned = [r for rid in entry.assignments.values() if (r := problem.resources.get(rid)) is not None]
        if len(assigned) != len(entry.assignments):
            blocked.add(tid)
            continue
        # Push past unavailability until every assigned resource is free.
        while True:
            end = start + task.duration
            pushed = start
            for res in assigned:
                if end > res.available.end:
                    pushed = -1
                    break
                pushed = max(pushed, res.available.start)
                for w in res.blocked:
                    if w.overlaps(start, end):
                        pushed = max(pushed, w.end)
            if pushed == -1:
                blocked.add(tid)
                break
            if pushed == start:
                starts[tid] = start
                break
            start = pushed

    entries = tuple(
        PlanEntry(task_id=tid, start=starts[tid], assignments=dict(ref[tid].assignments))
        for tid in sorted(starts, key=lambda t: (starts[t], t))
    )
    return Propagation(plan=Plan(entries=entries), blocked=frozenset(blocked), resource_edges=tuple(chain))
