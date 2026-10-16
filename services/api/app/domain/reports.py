"""API-facing result models produced by analysis, solver and evaluation."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.models import Patch, Plan
from app.domain.violations import Violation


class Out(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class TaskStatus(StrEnum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"  # downstream of the disruption, but slack absorbs it
    DELAYED = "delayed"  # realized later start, deadline still met
    BREACH = "breach"  # misses a hard deadline
    BLOCKED = "blocked"  # cannot be scheduled at all without intervention


class Binding(Out):
    """The constraint that pins a task's start time (why it cannot start earlier)."""

    kind: Literal["release", "precedence", "resource", "availability", "pinned", "free"]
    constraint_id: str | None
    text: str
    via: str | None = None  # predecessor task or resource id


class TaskTiming(Out):
    task_id: str
    start: int
    end: int
    duration: int
    assignments: dict[str, str]
    slack: int | None
    binding: Binding


class TaskImpact(Out):
    task_id: str
    status: TaskStatus
    wave: int | None
    reference_start: int
    start: int | None
    delay: int | None


class CausalEdge(Out):
    from_id: str
    to_id: str
    kind: Literal["precedence", "resource"]
    wave: int


class ScheduleMetrics(Out):
    readiness: int | None  # start of the deadline milestone
    deadline: int
    deadline_delta: int | None  # readiness - deadline; > 0 means late
    driving_path: list[str]


class ImpactMetrics(Out):
    at_risk_count: int
    delayed_count: int
    breach_count: int
    blocked_count: int
    total_delay_minutes: int
    conflicts_if_unchanged: int


class ImpactReport(Out):
    sources: list[str]
    tasks: list[TaskImpact]
    causal_edges: list[CausalEdge]
    timings: list[TaskTiming]
    schedule: ScheduleMetrics
    metrics: ImpactMetrics
    conflicts_if_unchanged: list[Violation]


class TaskChange(Out):
    task_id: str
    moved_minutes: int | None
    reassigned: list[tuple[str, str | None, str]]  # (requirement, from, to)
    duration_from: int | None = None
    duration_to: int | None = None
    deferred: bool = False


class ServiceImpact(Out):
    kind: Literal["compress", "defer"]
    task_id: str
    text: str
    severity: float  # compress: share of the compressible range used (0-1]; defer: 2 (scope cut)


class SolverInfo(Out):
    status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "UNKNOWN", "NOT_RUN"]
    wall_ms: int
    objective: int | None = None


class EvaluationStatus(StrEnum):
    VERIFIED = "verified"  # feasible plan found and independently validated
    INFEASIBLE = "infeasible"  # proven: no plan satisfies hard constraints with this patch
    REJECTED = "rejected"  # patch itself is malformed / not permitted
    UNKNOWN = "unknown"  # solver timed out without proof either way


class InfeasibilityFacts(Out):
    best_readiness: int | None  # with the deadline relaxed
    best_delta: int | None
    precedence_bound: int  # readiness ignoring resources entirely
    bound_chain: list[str]
    reasons: list[str]


class Evaluation(Out):
    status: EvaluationStatus
    patch: Patch
    violations: list[Violation]
    plan: Plan | None
    timings: list[TaskTiming]
    schedule: ScheduleMetrics | None
    changes: list[TaskChange]
    cost_cents: int
    service_impacts: list[ServiceImpact]
    disruption_minutes: int
    reassignments: int
    solver: SolverInfo
    infeasibility: InfeasibilityFacts | None = None
    proven_optimal: bool = False
