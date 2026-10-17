"""Use cases behind the HTTP API. Routers stay thin; all verification lives here or below."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.core.errors import ApiError
from app.domain.analysis import impact_report, schedule_timings
from app.domain.effective import EffectiveProblem, InvalidShockError, compile_problem
from app.domain.models import Patch, Plan, Scenario, Shock
from app.domain.notice import ChangeNotice, build_notice
from app.domain.preferences import PreferenceReport, Preferences
from app.domain.ranking import rank_options
from app.domain.reports import Evaluation, ImpactReport, ScheduleMetrics, TaskTiming
from app.domain.revision import Revision, RevisionState, make_revision, merge_committed, revision_id
from app.domain.validate import validate_plan
from app.fixtures import load_scenario
from app.solver.evaluate import evaluate_patch
from app.solver.search import MenuItem, search_recoveries


class Out(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class PlanView(Out):
    timings: list[TaskTiming]
    schedule: ScheduleMetrics


class RevisionView(Out):
    revision: Revision
    verified: bool  # current plan satisfies every hard constraint for this revision
    impact: ImpactReport | None  # present when the plan no longer holds (after a shock)
    plan_view: PlanView | None  # present when verified


class SearchOption(Out):
    id: str
    rank: int
    menu_items: list[MenuItem]
    evaluation: Evaluation
    report: PreferenceReport
    touched: tuple[str, ...]


class SearchResponse(Out):
    base_revision_id: str
    source: str  # always "deterministic-search": never presented as AI output
    options: list[SearchOption]
    combinations_tried: int
    solver_ms: int


def verify_revision(revision: Revision) -> Scenario:
    """Reject tampered or foreign revisions; return the scenario they belong to."""
    if revision_id(revision.state) != revision.id:
        raise ApiError(400, "INVALID_REVISION", "Revision id does not match its content.")
    try:
        scenario = load_scenario(revision.state.scenario_id)
    except KeyError as exc:
        raise ApiError(400, "INVALID_REVISION", "Unknown scenario.") from exc
    if scenario.version != revision.state.scenario_version:
        raise ApiError(400, "INVALID_REVISION", "Scenario version mismatch.")
    return scenario


def _problem(scenario: Scenario, shocks: tuple[Shock, ...], committed: Patch) -> EffectiveProblem:
    try:
        problem, static = compile_problem(scenario, shocks, committed)
    except InvalidShockError as exc:
        raise ApiError(422, "INVALID_SHOCK", str(exc)) from exc
    if problem is None:
        raise ApiError(
            400, "INVALID_REVISION", "Committed interventions are invalid.", [v.model_dump() for v in static]
        )
    return problem


def ensure_plan_shape(problem: EffectiveProblem, plan: Plan) -> None:
    """Reject forged revisions whose plan does not schedule exactly the scenario's tasks."""
    entries = [e.task_id for e in plan.entries]
    if len(entries) != len(set(entries)) or set(entries) != set(problem.tasks):
        raise ApiError(400, "INVALID_REVISION", "The revision's plan does not match the scenario.")


def load_problem(scenario: Scenario, revision: Revision) -> EffectiveProblem:
    """Compile the revision's problem and check its plan's shape (shared by every endpoint)."""
    state = revision.state
    problem = _problem(scenario, state.shocks, state.committed)
    ensure_plan_shape(problem, state.plan)
    return problem


def view(revision: Revision) -> RevisionView:
    scenario = verify_revision(revision)
    state = revision.state
    problem = load_problem(scenario, revision)
    violations = validate_plan(problem, state.plan)
    if not violations:
        timings, schedule = schedule_timings(problem, state.plan)
        return RevisionView(
            revision=revision, verified=True, impact=None, plan_view=PlanView(timings=timings, schedule=schedule)
        )
    return RevisionView(revision=revision, verified=False, impact=impact_report(problem, state.plan), plan_view=None)


def add_shock(revision: Revision, shock: Shock) -> RevisionView:
    verify_revision(revision)
    state = revision.state
    if len(state.shocks) >= 4:
        raise ApiError(422, "INVALID_SHOCK", "At most 4 disruptions per scenario; reset to start over.")
    new_state = RevisionState(
        scenario_id=state.scenario_id,
        scenario_version=state.scenario_version,
        shocks=(*state.shocks, shock),
        committed=state.committed,
        plan=state.plan,
        parent_id=revision.id,
        source="shock",
    )
    return view(make_revision(new_state))


def evaluate(revision: Revision, patch: Patch) -> Evaluation:
    scenario = verify_revision(revision)
    state = revision.state
    load_problem(scenario, revision)
    return evaluate_patch(scenario, state.shocks, state.committed, patch, state.plan)


def search(revision: Revision, preferences: Preferences | None = None) -> SearchResponse:
    scenario = verify_revision(revision)
    state = revision.state
    problem = load_problem(scenario, revision)
    result = search_recoveries(scenario, state.shocks, state.committed, state.plan)
    combos = {f"search-{i + 1}": combo for i, combo in enumerate(result.verified)}
    ranked = rank_options(
        [(f"search-{i + 1}", ev) for i, ev in enumerate(result.evaluations)],
        preferences or Preferences(),
        problem,
        state.plan,
    )
    options = [
        SearchOption(
            id=r.id,
            rank=r.rank,
            menu_items=list(combos[r.id]),
            evaluation=r.evaluation,
            report=r.report,
            touched=r.touched,
        )
        for r in ranked
    ]
    return SearchResponse(
        base_revision_id=revision.id,
        source="deterministic-search",
        options=options,
        combinations_tried=result.combinations_tried,
        solver_ms=result.solver_ms,
    )


def apply(revision: Revision, base_revision_id: str, patch: Patch, plan: Plan) -> RevisionView:
    """Commit a plan only after re-verifying it from scratch against the current revision."""
    scenario = verify_revision(revision)
    if base_revision_id != revision.id:
        raise ApiError(409, "STALE_REVISION", "This option was computed for an older revision. Re-run recovery.")
    state = revision.state
    committed = merge_committed(state.committed, patch)
    merged_for_check = Patch(actions=(*committed.actions, *(a for a in patch.actions if a not in committed.actions)))
    problem = _problem(scenario, state.shocks, merged_for_check)
    violations = validate_plan(problem, plan)
    if violations:
        raise ApiError(422, "PLAN_INVALID", "Plan violates hard constraints.", [v.model_dump() for v in violations])
    new_state = RevisionState(
        scenario_id=state.scenario_id,
        scenario_version=state.scenario_version,
        shocks=state.shocks,
        committed=committed,
        plan=plan,
        parent_id=revision.id,
        source="apply",
    )
    result = view(make_revision(new_state))
    if not result.verified:  # defensive: pins/assignments are encoded in the plan itself
        raise ApiError(500, "INTERNAL", "Applied plan failed re-verification.")
    return result


def notice(revision: Revision, patch: Patch, plan: Plan) -> ChangeNotice:
    """Who must be told what, for a verified plan relative to the plan people currently hold."""
    scenario = verify_revision(revision)
    state = revision.state
    merged = Patch(actions=(*state.committed.actions, *(a for a in patch.actions if a not in state.committed.actions)))
    problem = _problem(scenario, state.shocks, merged)
    violations = validate_plan(problem, plan)
    if violations:
        raise ApiError(422, "PLAN_INVALID", "Plan violates hard constraints.", [v.model_dump() for v in violations])
    return build_notice(problem, state.plan, plan, patch, now=0)
