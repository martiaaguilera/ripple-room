"""CP-SAT scheduling model for one effective problem.

Model
-----
* one integer start per task, ``end = start + duration``;
* each requirement picks exactly one eligible *active* resource (boolean literal
  + optional interval), and a resource never fills two slots of one task;
* every resource is a capacity-1 ``NoOverlap`` over its optional intervals plus
  fixed intervals for time outside its availability and for shock windows;
* precedence ``start(b) >= end(a) + lag``; releases; hard deadlines (optionally
  relaxed into a lateness objective for infeasibility diagnostics);
* patch pins and forced assignments are hard equalities.

Objective (deadlines enforced): minimise disruption against the reference plan,
``sum |start - ref_start| + REASSIGNMENT_WEIGHT * changed_assignments``.
Intervention cost is not a solver variable: it is fixed by the patch.

Determinism: single worker, fixed seed, deterministic time limit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from ortools.sat.python import cp_model

from app.domain.analysis import REASSIGNMENT_WEIGHT
from app.domain.effective import EffectiveProblem
from app.domain.models import MINUTES_PER_DAY, Plan, PlanEntry

SolverStatus = Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN"]

_STATUS: dict[cp_model.CpSolverStatus, SolverStatus] = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN: "UNKNOWN",
}


@dataclass(frozen=True)
class SolveConfig:
    max_time_seconds: float = 5.0
    max_deterministic_time: float = 4.0
    seed: int = 7


@dataclass(frozen=True)
class SolveResult:
    status: SolverStatus
    plan: Plan | None
    objective: int | None
    wall_ms: int


def solve(
    problem: EffectiveProblem,
    reference: Plan | None,
    *,
    enforce_deadlines: bool = True,
    config: SolveConfig | None = None,
) -> SolveResult:
    config = config or SolveConfig()
    ref = reference.by_task() if reference else {}
    model = cp_model.CpModel()
    horizon = MINUTES_PER_DAY

    starts: dict[str, cp_model.IntVar] = {}
    ends: dict[str, cp_model.IntVar] = {}
    for tid in sorted(problem.tasks):
        task = problem.tasks[tid]
        s = model.new_int_var(task.release, horizon, f"s_{tid}")
        e = model.new_int_var(task.release, horizon, f"e_{tid}")
        model.add(e == s + task.duration)
        starts[tid], ends[tid] = s, e
        if tid in problem.pins:
            model.add(s == problem.pins[tid])

    for dep in problem.dependencies:
        model.add(starts[dep.to_id] >= ends[dep.from_id] + dep.lag)

    lateness: list[cp_model.IntVar] = []
    for tid in sorted(problem.tasks):
        task = problem.tasks[tid]
        if task.deadline is None:
            continue
        if enforce_deadlines:
            model.add(ends[tid] <= task.deadline)
        else:
            late = model.new_int_var(0, horizon, f"late_{tid}")
            model.add(late >= ends[tid] - task.deadline)
            lateness.append(late)

    literals: dict[tuple[str, str, str], cp_model.IntVar] = {}
    intervals_by_resource: dict[str, list[cp_model.IntervalVar]] = {rid: [] for rid in problem.resources}
    changed: list[cp_model.LinearExprT] = []
    for tid in sorted(problem.tasks):
        task = problem.tasks[tid]
        per_resource: dict[str, list[cp_model.IntVar]] = {}
        for req in task.requirements:
            eligible = problem.eligible(req)
            forced = problem.assigns.get((tid, req.id))
            if forced is not None:
                eligible = [r for r in eligible if r == forced]
            if not eligible:
                model.add_bool_or([])  # no eligible resource: provably infeasible
                continue
            lits = []
            for rid in eligible:
                lit = model.new_bool_var(f"x_{tid}_{req.id}_{rid}")
                interval = model.new_optional_interval_var(
                    starts[tid], task.duration, ends[tid], lit, f"i_{tid}_{req.id}_{rid}"
                )
                if task.duration > 0:
                    intervals_by_resource[rid].append(interval)
                literals[(tid, req.id, rid)] = lit
                per_resource.setdefault(rid, []).append(lit)
                lits.append(lit)
            model.add_exactly_one(lits)
            ref_rid = ref[tid].assignments.get(req.id) if tid in ref else None
            if ref_rid is not None:
                keep = literals.get((tid, req.id, ref_rid))
                changed.append(1 if keep is None else 1 - keep)
        for lits in per_resource.values():
            if len(lits) > 1:
                model.add_at_most_one(lits)

    for rid, res in problem.resources.items():
        fixed: list[tuple[int, int]] = []
        if res.available.start > 0:
            fixed.append((0, res.available.start))
        if res.available.end < horizon:
            fixed.append((res.available.end, horizon))
        fixed += [(w.start, w.end) for w in res.blocked]
        for i, (a, b) in enumerate(fixed):
            intervals_by_resource[rid].append(model.new_fixed_size_interval_var(a, b - a, f"blk_{rid}_{i}"))
        if len(intervals_by_resource[rid]) > 1:
            model.add_no_overlap(intervals_by_resource[rid])

    deviation: list[cp_model.IntVar] = []
    for tid in sorted(problem.tasks):
        if tid not in ref:
            continue
        dev = model.new_int_var(0, horizon, f"dev_{tid}")
        model.add_abs_equality(dev, starts[tid] - ref[tid].start)
        deviation.append(dev)
        model.add_hint(starts[tid], max(ref[tid].start, problem.tasks[tid].release))

    disruption = cp_model.LinearExpr.sum(deviation) + REASSIGNMENT_WEIGHT * cp_model.LinearExpr.sum(changed)
    if enforce_deadlines:
        model.minimize(disruption)
    else:
        # Lateness dominates: one minute late outweighs any disruption.
        model.minimize(
            cp_model.LinearExpr.sum(lateness) * (horizon * (len(problem.tasks) + 1) * REASSIGNMENT_WEIGHT) + disruption
        )

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = config.seed
    solver.parameters.max_time_in_seconds = config.max_time_seconds
    solver.parameters.max_deterministic_time = config.max_deterministic_time
    t0 = time.perf_counter()
    code = solver.solve(model)
    wall_ms = round((time.perf_counter() - t0) * 1000)
    status = _STATUS.get(code, "UNKNOWN")
    if status not in ("OPTIMAL", "FEASIBLE"):
        return SolveResult(status=status, plan=None, objective=None, wall_ms=wall_ms)

    entries: list[PlanEntry] = []
    for tid in sorted(problem.tasks, key=lambda t: (solver.value(starts[t]), t)):
        assignments = {
            req.id: rid
            for req in problem.tasks[tid].requirements
            for rid in problem.eligible(req)
            if (chosen := literals.get((tid, req.id, rid))) is not None and solver.boolean_value(chosen)
        }
        entries.append(PlanEntry(task_id=tid, start=solver.value(starts[tid]), assignments=assignments))
    return SolveResult(
        status=status,
        plan=Plan(entries=tuple(entries)),
        objective=round(solver.objective_value),
        wall_ms=wall_ms,
    )
