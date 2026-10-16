"""Canonical domain model for Ripple Room scenarios.

Time convention: every time value is an integer number of minutes since the
scenario epoch (00:00 local time on ``Scenario.date`` in ``Scenario.timezone``).
Fixtures may write times as ``"HH:MM"``; they are normalized to minutes on load.
Money is stored as integer minor units (cents) together with a currency code.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.domain.graph import topological_order

MINUTES_PER_DAY = 24 * 60
_HHMM = re.compile(r"^(\d{1,2}):(\d{2})$")


def _parse_clock(value: object) -> object:
    if isinstance(value, str):
        match = _HHMM.match(value)
        if not match:
            raise ValueError(f"expected HH:MM, got {value!r}")
        hours, minutes = int(match.group(1)), int(match.group(2))
        if hours > 24 or minutes > 59:
            raise ValueError(f"invalid clock time {value!r}")
        return hours * 60 + minutes
    return value


Minute = Annotated[int, BeforeValidator(_parse_clock), Field(ge=0, le=MINUTES_PER_DAY)]
Duration = Annotated[int, Field(ge=0, le=MINUTES_PER_DAY)]
Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,47}$")]


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Window(Frozen):
    start: Minute
    end: Minute

    @model_validator(mode="after")
    def _ordered(self) -> Window:
        if self.end <= self.start:
            raise ValueError("window end must be after start")
        return self

    def overlaps(self, start: int, end: int) -> bool:
        return start < self.end and self.start < end


class Zone(Frozen):
    id: Identifier
    label: str
    order: int = Field(ge=0, description="Left-to-right layout order on the canvas")


class ResourceKind(StrEnum):
    PERSON = "person"
    EQUIPMENT = "equipment"
    SPACE = "space"


class Resource(Frozen):
    id: Identifier
    label: str
    kind: ResourceKind
    skills: tuple[str, ...]
    available: Window
    standby: bool = Field(
        default=False,
        description="Standby resources only exist in a plan after an activate_resource intervention.",
    )
    activation_cost_cents: int = Field(default=0, ge=0)
    hourly_cost_cents: int = Field(default=0, ge=0)
    note: str = ""


class Requirement(Frozen):
    """One resource slot a task needs for its whole duration (capacity 1)."""

    id: Identifier
    skill: str


class Task(Frozen):
    id: Identifier
    label: str
    zone_id: Identifier
    duration: Duration
    min_duration: Duration | None = Field(
        default=None, description="If set, the task may be compressed down to this duration."
    )
    compress_note: str = ""
    release: Minute = Field(description="Earliest allowed start.")
    deadline: Minute | None = Field(default=None, description="Hard latest finish.")
    optional: bool = False
    defer_note: str = ""
    milestone: bool = False
    requirements: tuple[Requirement, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Task:
        if self.milestone and (self.duration != 0 or self.requirements):
            raise ValueError(f"milestone {self.id} must have zero duration and no requirements")
        if self.min_duration is not None and not (0 < self.min_duration < self.duration):
            raise ValueError(f"task {self.id}: min_duration must be in (0, duration)")
        req_ids = [r.id for r in self.requirements]
        if len(req_ids) != len(set(req_ids)):
            raise ValueError(f"task {self.id}: duplicate requirement ids")
        return self


class Dependency(Frozen):
    from_id: Identifier
    to_id: Identifier
    lag: Duration = 0
    waived_if_deferred: bool = Field(
        default=False,
        description="If the predecessor is deferred, the successor no longer waits for it.",
    )


class PlanEntry(Frozen):
    task_id: Identifier
    start: Minute
    assignments: dict[str, Identifier] = Field(default_factory=dict, description="requirement id -> resource id")


class Plan(Frozen):
    entries: tuple[PlanEntry, ...]

    def by_task(self) -> dict[str, PlanEntry]:
        return {e.task_id: e for e in self.entries}


class Scenario(Frozen):
    id: Identifier
    version: str
    name: str
    venue: str
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    timezone: str
    currency: Literal["EUR"] = "EUR"
    deadline_task_id: Identifier
    zones: tuple[Zone, ...]
    resources: tuple[Resource, ...]
    tasks: tuple[Task, ...]
    dependencies: tuple[Dependency, ...]
    baseline: Plan
    disclaimer: str = "Fictional, simulated scenario."

    def task(self, task_id: str) -> Task:
        for t in self.tasks:
            if t.id == task_id:
                return t
        raise KeyError(task_id)

    def resource(self, resource_id: str) -> Resource:
        for r in self.resources:
            if r.id == resource_id:
                return r
        raise KeyError(resource_id)

    @model_validator(mode="after")
    def _referential_integrity(self) -> Scenario:
        task_ids = {t.id for t in self.tasks}
        zone_ids = {z.id for z in self.zones}
        resource_ids = {r.id for r in self.resources}
        if len(task_ids) != len(self.tasks):
            raise ValueError("duplicate task ids")
        if len(resource_ids) != len(self.resources):
            raise ValueError("duplicate resource ids")
        if self.deadline_task_id not in task_ids:
            raise ValueError("deadline_task_id must reference a task")
        for t in self.tasks:
            if t.zone_id not in zone_ids:
                raise ValueError(f"task {t.id} references unknown zone {t.zone_id}")
        for d in self.dependencies:
            if d.from_id not in task_ids or d.to_id not in task_ids:
                raise ValueError(f"dependency {d.from_id}->{d.to_id} references unknown task")
            if d.from_id == d.to_id:
                raise ValueError(f"self-dependency on {d.from_id}")
        topological_order(task_ids, [(d.from_id, d.to_id) for d in self.dependencies])  # raises on cycles
        for e in self.baseline.entries:
            if e.task_id not in task_ids:
                raise ValueError(f"baseline references unknown task {e.task_id}")
            for rid in e.assignments.values():
                if rid not in resource_ids:
                    raise ValueError(f"baseline references unknown resource {rid}")
        return self


# --- Disruptions ("shocks") -------------------------------------------------


class TaskDelayShock(Frozen):
    """The earliest start of a task (typically an arrival milestone) moves later."""

    kind: Literal["task_delay"] = "task_delay"
    task_id: Identifier
    delay_minutes: int = Field(ge=1, le=240)


class ResourceUnavailableShock(Frozen):
    """A resource cannot work during a window."""

    kind: Literal["resource_unavailable"] = "resource_unavailable"
    resource_id: Identifier
    window: Window


Shock = Annotated[TaskDelayShock | ResourceUnavailableShock, Field(discriminator="kind")]


# --- Interventions (the only edits a recovery plan may make) ---------------


class ActivateResource(Frozen):
    type: Literal["activate_resource"] = "activate_resource"
    resource_id: Identifier


class CompressTask(Frozen):
    type: Literal["compress_task"] = "compress_task"
    task_id: Identifier
    duration: Duration


class DeferTask(Frozen):
    """Move an optional task out of the pre-doors plan."""

    type: Literal["defer_task"] = "defer_task"
    task_id: Identifier


class AssignResource(Frozen):
    type: Literal["assign_resource"] = "assign_resource"
    task_id: Identifier
    requirement_id: Identifier
    resource_id: Identifier


class PinStart(Frozen):
    type: Literal["pin_start"] = "pin_start"
    task_id: Identifier
    start: Minute


Intervention = Annotated[
    ActivateResource | CompressTask | DeferTask | AssignResource | PinStart,
    Field(discriminator="type"),
]


class Patch(Frozen):
    actions: tuple[Intervention, ...] = Field(default=(), max_length=24)
    rationale: str = Field(default="", max_length=600)
