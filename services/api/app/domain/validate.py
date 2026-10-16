"""Independent plan validator.

Deliberately implemented without OR-Tools: every plan the solver returns is
re-checked here, so a modelling bug in the solver cannot surface as a green
"feasible" badge.
"""

from __future__ import annotations

import itertools
from collections import defaultdict

from app.domain.effective import EffectiveProblem
from app.domain.models import Plan
from app.domain.violations import Violation


def validate_plan(problem: EffectiveProblem, plan: Plan, *, check_deadlines: bool = True) -> list[Violation]:
    out: list[Violation] = []
    entries = plan.by_task()
    if len(entries) != len(plan.entries):
        out.append(Violation.of("DUPLICATE_ENTRY", "plan", "A task appears more than once in the plan."))

    for task_id in sorted(set(entries) - set(problem.tasks)):
        reason = "deferred" if task_id in problem.deferred else "unknown"
        out.append(
            Violation.of(
                "UNEXPECTED_TASK", f"plan:{task_id}", f"Plan schedules {reason} task '{task_id}'.", task_id=task_id
            )
        )

    usage: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for task in problem.tasks.values():
        entry = entries.get(task.id)
        if entry is None:
            out.append(
                Violation.of("MISSING_TASK", f"plan:{task.id}", f"{task.label} is not scheduled.", task_id=task.id)
            )
            continue
        start, end = entry.start, entry.start + task.duration
        if start < task.release:
            out.append(
                Violation.of(
                    "RELEASE",
                    f"release:{task.id}",
                    f"{task.label} starts before it can ({start} < {task.release}).",
                    task_id=task.id,
                )
            )
        if check_deadlines and task.deadline is not None and end > task.deadline:
            out.append(
                Violation.of(
                    "DEADLINE",
                    f"deadline:{task.id}",
                    f"{task.label} finishes {end - task.deadline} min after its hard deadline.",
                    task_id=task.id,
                )
            )
        pinned = problem.pins.get(task.id)
        if pinned is not None and pinned != start:
            out.append(
                Violation.of(
                    "PIN",
                    f"patch:{task.id}",
                    f"{task.label} was pinned to {pinned} but starts at {start}.",
                    task_id=task.id,
                )
            )

        req_ids = {r.id for r in task.requirements}
        for extra in sorted(set(entry.assignments) - req_ids):
            out.append(
                Violation.of(
                    "UNKNOWN_REQUIREMENT",
                    f"skill:{task.id}:{extra}",
                    f"{task.label} has no '{extra}' slot.",
                    task_id=task.id,
                )
            )
        used_here: set[str] = set()
        for req in task.requirements:
            rid = entry.assignments.get(req.id)
            if rid is None:
                out.append(
                    Violation.of(
                        "MISSING_ASSIGNMENT",
                        f"skill:{task.id}:{req.id}",
                        f"{task.label} has no resource for '{req.id}'.",
                        task_id=task.id,
                    )
                )
                continue
            forced = problem.assigns.get((task.id, req.id))
            if forced is not None and forced != rid:
                out.append(
                    Violation.of(
                        "PIN",
                        f"patch:{task.id}:{req.id}",
                        f"{task.label} must use {forced} for '{req.id}'.",
                        task_id=task.id,
                        resource_id=rid,
                    )
                )
            res = problem.resources.get(rid)
            if res is None:
                out.append(
                    Violation.of(
                        "RESOURCE_INACTIVE",
                        f"standby:{rid}",
                        f"{task.label} uses '{rid}', which is not active in this plan.",
                        task_id=task.id,
                        resource_id=rid,
                    )
                )
                continue
            if req.skill not in res.skills:
                out.append(
                    Violation.of(
                        "SKILL_MISMATCH",
                        f"skill:{task.id}:{req.id}",
                        f"{res.label} lacks skill '{req.skill}'.",
                        task_id=task.id,
                        resource_id=rid,
                    )
                )
            if rid in used_here:
                out.append(
                    Violation.of(
                        "DOUBLE_BOOKED_IN_TASK",
                        f"overlap:{rid}",
                        f"{res.label} fills two slots of {task.label}.",
                        task_id=task.id,
                        resource_id=rid,
                    )
                )
            used_here.add(rid)
            if not res.free_during(start, end):
                out.append(
                    Violation.of(
                        "RESOURCE_UNAVAILABLE",
                        f"avail:{rid}",
                        f"{res.label} is not available for {task.label} at that time.",
                        task_id=task.id,
                        resource_id=rid,
                    )
                )
            if end > start:
                usage[rid].append((start, end, task.id))

    for dep in problem.dependencies:
        a, b = entries.get(dep.from_id), entries.get(dep.to_id)
        if a is None or b is None:
            continue
        a_end = a.start + problem.tasks[dep.from_id].duration
        if b.start < a_end + dep.lag:
            out.append(
                Violation.of(
                    "PRECEDENCE",
                    f"prec:{dep.from_id}->{dep.to_id}",
                    f"{problem.tasks[dep.to_id].label} starts before {problem.tasks[dep.from_id].label} is done.",
                    task_id=dep.to_id,
                )
            )

    for rid, intervals in sorted(usage.items()):
        intervals.sort()
        for (_s1, e1, t1), (s2, _e2, t2) in itertools.pairwise(intervals):
            if s2 < e1:
                out.append(
                    Violation.of(
                        "RESOURCE_OVERLAP",
                        f"overlap:{rid}",
                        f"{problem.resources[rid].label} is double-booked on {problem.tasks[t1].label} and {problem.tasks[t2].label}.",
                        task_id=t2,
                        resource_id=rid,
                    )
                )
    return out
