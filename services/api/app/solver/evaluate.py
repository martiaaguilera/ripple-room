"""The authoritative verdict on a candidate intervention patch.

Pipeline: static patch checks -> CP-SAT (hard deadlines) -> independent
validator re-check -> explanation facts. A model (LLM) can propose patches,
but only this function can call one ``verified``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.analysis import (
    REASSIGNMENT_WEIGHT,
    fmt_clock,
    intervention_cost_cents,
    plan_changes,
    precedence_bound,
    schedule_timings,
    service_impacts,
)
from app.domain.effective import EffectiveProblem, compile_problem
from app.domain.models import Patch, Plan, Scenario, Shock
from app.domain.reports import (
    Evaluation,
    EvaluationStatus,
    InfeasibilityFacts,
    SolverInfo,
)
from app.domain.validate import validate_plan
from app.domain.violations import Violation
from app.solver.cpsat import SolveConfig, solve


class VerifierInconsistencyError(RuntimeError):
    """The solver returned a plan the independent validator rejects (a bug, never shown as feasible)."""


def merge_patches(committed: Patch, candidate: Patch) -> Patch:
    return Patch(actions=committed.actions + candidate.actions, rationale=candidate.rationale)


def _infeasibility(problem: EffectiveProblem, reference: Plan, config: SolveConfig) -> InfeasibilityFacts:
    bound, chain = precedence_bound(problem)
    deadline_task = problem.scenario.task(problem.scenario.deadline_task_id)
    deadline = deadline_task.deadline
    reasons: list[str] = []
    relaxed = solve(problem, reference, enforce_deadlines=False, config=config)
    best: int | None = None
    if relaxed.plan is not None:
        if validate_plan(problem, relaxed.plan, check_deadlines=False):
            raise VerifierInconsistencyError("relaxed plan failed validation")
        best = relaxed.plan.by_task()[deadline_task.id].start
    if deadline is not None and bound > deadline:
        labels = " → ".join(problem.tasks[t].label for t in chain if not problem.tasks[t].milestone or t == chain[0])
        reasons.append(
            f"Even with unlimited crew and equipment, the chain {labels} cannot be ready before "
            f"{fmt_clock(bound)} ({bound - deadline} min after the {fmt_clock(deadline)} deadline)."
        )
    elif best is not None and deadline is not None:
        reasons.append(
            f"Dependencies alone would allow readiness at {fmt_clock(bound)}, but crew, equipment and "
            f"space limits push the best achievable readiness to {fmt_clock(best)} "
            f"({best - deadline} min late)."
        )
    for task in problem.tasks.values():
        for req in task.requirements:
            if not problem.eligible(req):
                reasons.append(f"No active resource can cover '{req.skill}' for {task.label}.")
    return InfeasibilityFacts(
        best_readiness=best,
        best_delta=None if best is None or deadline is None else best - deadline,
        precedence_bound=bound,
        bound_chain=chain,
        reasons=reasons,
    )


def _empty(status: EvaluationStatus, patch: Patch, violations: list[Violation], solver: SolverInfo) -> Evaluation:
    return Evaluation(
        status=status,
        patch=patch,
        violations=violations,
        plan=None,
        timings=[],
        schedule=None,
        changes=[],
        cost_cents=0,
        service_impacts=[],
        disruption_minutes=0,
        reassignments=0,
        solver=solver,
    )


def evaluate_patch(
    scenario: Scenario,
    shocks: Sequence[Shock],
    committed: Patch,
    candidate: Patch,
    reference: Plan,
    *,
    config: SolveConfig | None = None,
    explain_infeasible: bool = True,
) -> Evaluation:
    config = config or SolveConfig()
    merged = merge_patches(committed, candidate)
    problem, static = compile_problem(scenario, shocks, merged)
    if problem is None:
        return _empty(EvaluationStatus.REJECTED, candidate, static, SolverInfo(status="NOT_RUN", wall_ms=0))

    result = solve(problem, reference, config=config)
    solver_info = SolverInfo(status=result.status, wall_ms=result.wall_ms, objective=result.objective)
    if result.status == "UNKNOWN":
        return _empty(EvaluationStatus.UNKNOWN, candidate, [], solver_info)
    if result.plan is None:
        ev = _empty(EvaluationStatus.INFEASIBLE, candidate, [], solver_info)
        if not explain_infeasible:
            return ev
        return ev.model_copy(update={"infeasibility": _infeasibility(problem, reference, config)})

    violations = validate_plan(problem, result.plan)
    if violations:
        raise VerifierInconsistencyError("; ".join(v.message for v in violations))

    timings, schedule = schedule_timings(problem, result.plan)
    changes, moved, reassigned = plan_changes(scenario, problem, result.plan, reference)
    return Evaluation(
        status=EvaluationStatus.VERIFIED,
        patch=candidate,
        violations=[],
        plan=result.plan,
        timings=timings,
        schedule=schedule,
        changes=changes,
        cost_cents=intervention_cost_cents(problem, result.plan),
        service_impacts=service_impacts(scenario, problem),
        disruption_minutes=moved + REASSIGNMENT_WEIGHT * reassigned,
        reassignments=reassigned,
        solver=solver_info,
        proven_optimal=result.status == "OPTIMAL",
    )
