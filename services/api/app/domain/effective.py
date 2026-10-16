"""Compile scenario + shocks + intervention patch into one effective problem.

Both the CP-SAT solver and the independent plan validator consume the same
``EffectiveProblem``. That shared compilation step is what guarantees they
agree on semantics (durations, releases, active resources, blocked windows).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.domain.models import (
    ActivateResource,
    AssignResource,
    CompressTask,
    DeferTask,
    Dependency,
    Patch,
    PinStart,
    Requirement,
    Resource,
    ResourceUnavailableShock,
    Scenario,
    Shock,
    Task,
    TaskDelayShock,
    Window,
)
from app.domain.violations import Violation


class InvalidShockError(ValueError):
    """A shock references unknown entities or is otherwise malformed."""


@dataclass(frozen=True)
class EffTask:
    id: str
    label: str
    duration: int
    release: int
    deadline: int | None
    milestone: bool
    requirements: tuple[Requirement, ...]


@dataclass(frozen=True)
class EffResource:
    id: str
    label: str
    skills: frozenset[str]
    available: Window
    blocked: tuple[Window, ...]
    hourly_cost_cents: int
    activation_cost_cents: int
    activated: bool

    def free_during(self, start: int, end: int) -> bool:
        if start < self.available.start or end > self.available.end:
            return False
        if start == end:
            return True
        return not any(w.overlaps(start, end) for w in self.blocked)


@dataclass(frozen=True)
class EffectiveProblem:
    scenario: Scenario
    tasks: dict[str, EffTask]
    resources: dict[str, EffResource]
    dependencies: tuple[Dependency, ...]
    deferred: frozenset[str]
    compressed: dict[str, int]
    pins: dict[str, int]
    assigns: dict[tuple[str, str], str]
    activated: frozenset[str]
    shocks: tuple[Shock, ...] = field(default=())

    def eligible(self, requirement: Requirement) -> list[str]:
        """Active resources holding the requirement's skill, in stable id order."""
        return sorted(r.id for r in self.resources.values() if requirement.skill in r.skills)


def validate_shocks(scenario: Scenario, shocks: Sequence[Shock]) -> None:
    task_ids = {t.id for t in scenario.tasks}
    resource_ids = {r.id for r in scenario.resources}
    for shock in shocks:
        if isinstance(shock, TaskDelayShock) and shock.task_id not in task_ids:
            raise InvalidShockError(f"unknown task {shock.task_id!r}")
        if isinstance(shock, ResourceUnavailableShock) and shock.resource_id not in resource_ids:
            raise InvalidShockError(f"unknown resource {shock.resource_id!r}")


def _patch_violations(scenario: Scenario, patch: Patch) -> list[Violation]:
    tasks = {t.id: t for t in scenario.tasks}
    resources = {r.id: r for r in scenario.resources}
    activated = {a.resource_id for a in patch.actions if isinstance(a, ActivateResource)}
    deferred = {a.task_id for a in patch.actions if isinstance(a, DeferTask)}
    out: list[Violation] = []
    seen: set[tuple[str, ...]] = set()

    def unknown_task(task_id: str) -> bool:
        if task_id not in tasks:
            out.append(Violation.of("UNKNOWN_TASK", f"patch:{task_id}", f"Unknown task '{task_id}'.", task_id=task_id))
            return True
        return False

    for action in patch.actions:
        key: tuple[str, ...]
        match action:
            case ActivateResource(resource_id=rid):
                key = ("activate", rid)
                res = resources.get(rid)
                if res is None:
                    out.append(
                        Violation.of("UNKNOWN_RESOURCE", f"patch:{rid}", f"Unknown resource '{rid}'.", resource_id=rid)
                    )
                elif not res.standby:
                    out.append(
                        Violation.of(
                            "NOT_STANDBY",
                            f"standby:{rid}",
                            f"{res.label} is already part of the plan; only standby resources can be activated.",
                            resource_id=rid,
                        )
                    )
            case CompressTask(task_id=tid, duration=dur):
                key = ("compress", tid)
                if not unknown_task(tid):
                    task = tasks[tid]
                    if task.min_duration is None:
                        out.append(
                            Violation.of(
                                "NOT_COMPRESSIBLE", f"duration:{tid}", f"{task.label} cannot be shortened.", task_id=tid
                            )
                        )
                    elif not (task.min_duration <= dur < task.duration):
                        out.append(
                            Violation.of(
                                "DURATION_OUT_OF_RANGE",
                                f"duration:{tid}",
                                f"{task.label} may be shortened to {task.min_duration}-{task.duration - 1} min, not {dur}.",
                                task_id=tid,
                            )
                        )
            case DeferTask(task_id=tid):
                key = ("defer", tid)
                if not unknown_task(tid):
                    task = tasks[tid]
                    if not task.optional:
                        out.append(
                            Violation.of(
                                "NOT_OPTIONAL",
                                f"optional:{tid}",
                                f"{task.label} is required before doors open and cannot be deferred.",
                                task_id=tid,
                            )
                        )
                    for dep in scenario.dependencies:
                        if dep.from_id == tid and dep.to_id not in deferred and not dep.waived_if_deferred:
                            successor = tasks[dep.to_id]
                            out.append(
                                Violation.of(
                                    "DEFER_BREAKS_DEPENDENCY",
                                    f"prec:{dep.from_id}->{dep.to_id}",
                                    f"Deferring {task.label} leaves {successor.label} without its predecessor.",
                                    task_id=tid,
                                )
                            )
            case AssignResource(task_id=tid, requirement_id=req_id, resource_id=rid):
                key = ("assign", tid, req_id)
                if not unknown_task(tid):
                    task = tasks[tid]
                    req = next((r for r in task.requirements if r.id == req_id), None)
                    res = resources.get(rid)
                    if req is None:
                        out.append(
                            Violation.of(
                                "UNKNOWN_REQUIREMENT",
                                f"patch:{tid}:{req_id}",
                                f"{task.label} has no '{req_id}' slot.",
                                task_id=tid,
                            )
                        )
                    elif res is None:
                        out.append(
                            Violation.of(
                                "UNKNOWN_RESOURCE", f"patch:{rid}", f"Unknown resource '{rid}'.", resource_id=rid
                            )
                        )
                    elif req.skill not in res.skills:
                        out.append(
                            Violation.of(
                                "SKILL_MISMATCH",
                                f"skill:{tid}:{req_id}",
                                f"{res.label} lacks skill '{req.skill}' needed by {task.label}.",
                                task_id=tid,
                                resource_id=rid,
                            )
                        )
                    elif res.standby and rid not in activated:
                        out.append(
                            Violation.of(
                                "RESOURCE_INACTIVE",
                                f"standby:{rid}",
                                f"{res.label} is on standby; activate it before assigning work.",
                                task_id=tid,
                                resource_id=rid,
                            )
                        )
                    elif tid in deferred:
                        out.append(
                            Violation.of(
                                "CONFLICTING_ACTIONS",
                                f"patch:{tid}",
                                f"{task.label} is both deferred and assigned.",
                                task_id=tid,
                            )
                        )
            case PinStart(task_id=tid):
                key = ("pin", tid)
                if not unknown_task(tid):
                    task = tasks[tid]
                    if tid in deferred:
                        out.append(
                            Violation.of(
                                "CONFLICTING_ACTIONS",
                                f"patch:{tid}",
                                f"{task.label} is both deferred and pinned.",
                                task_id=tid,
                            )
                        )
        if key in seen:
            out.append(Violation.of("DUPLICATE_ACTION", "patch", f"Duplicate action {'/'.join(key)}."))
        seen.add(key)
    return out


def _resource(res: Resource, shocks: Sequence[Shock], activated: set[str]) -> EffResource:
    blocked = tuple(
        sorted(
            (s.window for s in shocks if isinstance(s, ResourceUnavailableShock) and s.resource_id == res.id),
            key=lambda w: (w.start, w.end),
        )
    )
    return EffResource(
        id=res.id,
        label=res.label,
        skills=frozenset(res.skills),
        available=res.available,
        blocked=blocked,
        hourly_cost_cents=res.hourly_cost_cents,
        activation_cost_cents=res.activation_cost_cents,
        activated=res.id in activated,
    )


def _task(task: Task, shocks: Sequence[Shock], compressed: dict[str, int]) -> EffTask:
    delay = sum(s.delay_minutes for s in shocks if isinstance(s, TaskDelayShock) and s.task_id == task.id)
    return EffTask(
        id=task.id,
        label=task.label,
        duration=compressed.get(task.id, task.duration),
        release=task.release + delay,
        deadline=task.deadline,
        milestone=task.milestone,
        requirements=task.requirements,
    )


def compile_problem(
    scenario: Scenario, shocks: Sequence[Shock] = (), patch: Patch | None = None
) -> tuple[EffectiveProblem | None, list[Violation]]:
    """Return the effective problem, or ``None`` plus violations if the patch is statically invalid."""
    validate_shocks(scenario, shocks)
    patch = patch or Patch()
    violations = _patch_violations(scenario, patch)
    if violations:
        return None, violations

    activated = {a.resource_id for a in patch.actions if isinstance(a, ActivateResource)}
    deferred = frozenset(a.task_id for a in patch.actions if isinstance(a, DeferTask))
    compressed = {a.task_id: a.duration for a in patch.actions if isinstance(a, CompressTask)}
    pins = {a.task_id: a.start for a in patch.actions if isinstance(a, PinStart)}
    assigns = {(a.task_id, a.requirement_id): a.resource_id for a in patch.actions if isinstance(a, AssignResource)}

    tasks = {t.id: _task(t, shocks, compressed) for t in scenario.tasks if t.id not in deferred}
    resources = {
        r.id: _resource(r, shocks, activated) for r in scenario.resources if not r.standby or r.id in activated
    }
    deps = tuple(d for d in scenario.dependencies if d.from_id in tasks and d.to_id in tasks)
    return (
        EffectiveProblem(
            scenario=scenario,
            tasks=tasks,
            resources=resources,
            dependencies=deps,
            deferred=deferred,
            compressed=compressed,
            pins=pins,
            assigns=assigns,
            activated=frozenset(activated),
            shocks=tuple(shocks),
        ),
        [],
    )
