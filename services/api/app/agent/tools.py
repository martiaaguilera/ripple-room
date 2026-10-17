"""Trusted tools the planner model may call.

Every argument is validated with a strict Pydantic model (unknown fields and
unknown tool names are rejected). Tool results are plain data; nothing the
model sends can mutate scenario state — ``evaluate_patch`` only registers a
read-only candidate that the human may later apply.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.feedback import combinable_partials, coverage
from app.domain.analysis import fmt_clock, impact_report
from app.domain.effective import EffectiveProblem
from app.domain.models import Intervention, Patch, Plan, Scenario, Shock, TaskDelayShock
from app.domain.preferences import Preferences, assess
from app.domain.ranking import do_nothing_plan, touched_tasks
from app.domain.reports import Evaluation, EvaluationStatus, ImpactReport
from app.domain.revision import Revision
from app.solver.evaluate import evaluate_patch
from app.solver.search import MenuItem, intervention_menu, search_recoveries

TOOL_GET_SITUATION = "get_situation"
TOOL_INSPECT_TASK = "inspect_task"
TOOL_LIST_INTERVENTIONS = "list_interventions"
TOOL_EVALUATE_PATCH = "evaluate_patch"
TOOL_SUBMIT_OPTIONS = "submit_options"
NO_CHANGE_ID = "c0"
PLAYBOOK_PREFIX = "p"
IDLE_MIN_MINUTES = 20


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NoArgs(Strict):
    pass


class InspectTaskArgs(Strict):
    task_id: str = Field(max_length=48)


class EvaluatePatchArgs(Strict):
    actions: list[Intervention] = Field(min_length=1, max_length=8)
    rationale: str = Field(default="", max_length=400)


class SubmittedOption(Strict):
    candidate_id: str = Field(max_length=16)
    title: str = Field(max_length=80)
    why: str = Field(max_length=400)


class SubmitOptionsArgs(Strict):
    options: list[SubmittedOption] = Field(max_length=3)
    summary: str = Field(max_length=600)


Phase = Literal["perceive", "diagnose", "plan", "verify", "revise", "present"]


@dataclass
class Candidate:
    id: str
    evaluation: Evaluation
    rationale: str
    origin: Literal["model", "playbook", "no_change"] = "model"


@dataclass
class AgentContext:
    scenario: Scenario
    revision: Revision
    problem: EffectiveProblem
    impact: ImpactReport
    menu: list[MenuItem]
    max_evaluations: int
    preferences: Preferences
    do_nothing: Plan
    candidates: dict[str, Candidate] = field(default_factory=dict)
    evaluations_used: int = 0
    rejected_or_infeasible: int = 0
    submitted: SubmitOptionsArgs | None = None

    @classmethod
    def build(
        cls,
        scenario: Scenario,
        revision: Revision,
        problem: EffectiveProblem,
        max_evaluations: int,
        preferences: Preferences | None = None,
    ) -> AgentContext:
        ctx = cls(
            scenario=scenario,
            revision=revision,
            problem=problem,
            impact=impact_report(problem, revision.state.plan),
            menu=intervention_menu(scenario),
            max_evaluations=max_evaluations,
            preferences=preferences or Preferences(),
            do_nothing=do_nothing_plan(problem, revision.state.plan),
        )
        # Hybrid: the deterministic playbook search contributes known, verified alternatives (p1..pn).
        # They are always in the final pool, so the system never does worse than the playbook; the
        # model's job is to understand priorities and find strategies the playbook cannot express.
        state = revision.state
        playbook = search_recoveries(scenario, state.shocks, state.committed, state.plan)
        absorbed = ctx.impact.schedule.deadline_delta is not None and ctx.impact.schedule.deadline_delta <= 0
        # An empty playbook patch means "reschedule only, no new resources"; when the delay is already
        # absorbed without rescheduling, c0 (registered below) covers it instead.
        pairs = [(c, e) for c, e in zip(playbook.verified, playbook.evaluations, strict=True) if c or not absorbed]
        for i, (combo, ev) in enumerate(pairs, start=1):
            label = " + ".join(item.label for item in combo) or "Reschedule only: no extra people, kit or cuts"
            ctx.candidates[f"{PLAYBOOK_PREFIX}{i}"] = Candidate(
                id=f"{PLAYBOOK_PREFIX}{i}", evaluation=ev, rationale=label, origin="playbook"
            )
        # If the incident is absorbed by slack, "change nothing" is itself a verified option (c0).
        # It is verified by the same pipeline as any proposal and does not use the model's budget.
        if ctx.impact.schedule.deadline_delta is not None and ctx.impact.schedule.deadline_delta <= 0:
            state = revision.state
            ev = evaluate_patch(
                scenario, state.shocks, state.committed, Patch(rationale="Keep the current plan."), state.plan
            )
            if ev.status == EvaluationStatus.VERIFIED:
                ctx.candidates[NO_CHANGE_ID] = Candidate(
                    id=NO_CHANGE_ID,
                    evaluation=ev,
                    rationale="Keep the current plan: slack absorbs the delay.",
                    origin="no_change",
                )
        return ctx


@dataclass(frozen=True)
class ToolOutcome:
    content: dict[str, Any]
    phase: Phase
    summary: str
    ok: bool
    candidate: Candidate | None = None
    terminal: bool = False


_ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "type": {
            "type": "string",
            "enum": ["activate_resource", "compress_task", "defer_task", "assign_resource", "pin_start", "add_helper"],
        },
        "resource_id": {"type": "string", "description": "activate_resource, assign_resource, add_helper"},
        "task_id": {
            "type": "string",
            "description": "compress_task, defer_task, assign_resource, pin_start, add_helper",
        },
        "duration": {
            "type": "integer",
            "description": "compress_task: any duration between the task minimum and nominal",
        },
        "requirement_id": {"type": "string", "description": "assign_resource: slot id such as crew, tech, lead"},
        "start": {"type": "string", "description": "pin_start: local time HH:MM"},
    },
    "required": ["type"],
}


def tool_specs() -> list[dict[str, Any]]:
    def fn(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"type": "function", "function": {"name": name, "description": description, "parameters": parameters}}

    empty = {"type": "object", "properties": {}}
    return [
        fn(
            TOOL_GET_SITUATION,
            "Plan after the disruption: deadline, driving path, tasks (with dependencies), resources, idle people,"
            " verified playbook options.",
            empty,
        ),
        fn(
            TOOL_INSPECT_TASK,
            "Details for one task: timing, slack, what blocks it from starting earlier, eligible resources.",
            {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"]},
        ),
        fn(
            TOOL_LIST_INTERVENTIONS,
            "Permitted intervention menu with costs and trade-offs, plus free-form action rules.",
            empty,
        ),
        fn(
            TOOL_EVALUATE_PATCH,
            "Run the deterministic constraint verifier on a candidate patch. The ONLY way to know whether a patch works.",
            {
                "type": "object",
                "properties": {
                    "actions": {"type": "array", "items": _ACTION_SCHEMA, "minItems": 1, "maxItems": 8},
                    "rationale": {"type": "string", "description": "One sentence: why this patch should help."},
                },
                "required": ["actions", "rationale"],
            },
        ),
        fn(
            TOOL_SUBMIT_OPTIONS,
            "Finish: present up to 3 VERIFIED candidates (by candidate_id) to the coordinator, best first.",
            {
                "type": "object",
                "properties": {
                    "options": {
                        "type": "array",
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "candidate_id": {"type": "string"},
                                "title": {"type": "string", "description": "<= 8 words"},
                                "why": {
                                    "type": "string",
                                    "description": "Trade-off in plain words, citing tasks/constraints.",
                                },
                            },
                            "required": ["candidate_id", "title", "why"],
                        },
                    },
                    "summary": {"type": "string"},
                },
                "required": ["options", "summary"],
            },
        ),
    ]


def _clean_actions(raw: Any) -> Any:
    """Drop null/empty optional fields models often add to flat action objects."""
    if isinstance(raw, dict) and isinstance(raw.get("actions"), list):
        raw = dict(raw)
        raw["actions"] = [
            {k: v for k, v in a.items() if v not in (None, "")} if isinstance(a, dict) else a for a in raw["actions"]
        ]
    return raw


def _shock_text(scenario: Scenario, shock: Shock) -> str:
    if isinstance(shock, TaskDelayShock):
        task = scenario.task(shock.task_id)
        return f"{task.label} delayed by {shock.delay_minutes} min (earliest now {fmt_clock(task.release + shock.delay_minutes)})"
    res = scenario.resource(shock.resource_id)
    return f"{res.label} unavailable {fmt_clock(shock.window.start)}-{fmt_clock(shock.window.end)}"


def tool_content_json(content: dict[str, Any]) -> str:
    """The exact text a tool result is sent to the model as: compact, UTF-8 (no \\u escapes), stable order."""
    return json.dumps(content, separators=(",", ":"), ensure_ascii=False)


def _named(item_id: str, label: str) -> dict[str, str]:
    """``id`` plus ``label`` only when the label says more than the id in words ("unload-truss" = "Unload truss")."""
    return {"id": item_id} if label.lower() == item_id.replace("-", " ") else {"id": item_id, "label": label}


def _span(start: int, duration: int) -> str:
    return fmt_clock(start) if duration == 0 else f"{fmt_clock(start)}-{fmt_clock(start + duration)}"


def _task_rows(ctx: AgentContext) -> list[dict[str, Any]]:
    """One row per active task. Defaults and empty fields are omitted; dependencies live on the task ("after")."""
    sc = ctx.scenario
    timings = {t.task_id: t for t in ctx.impact.timings}
    status = {t.task_id: t.status.value for t in ctx.impact.tasks}
    after: dict[str, list[str]] = {}
    for d in ctx.problem.dependencies:
        after.setdefault(d.to_id, []).append(d.from_id)
    rows = []
    for task in sc.tasks:
        if task.id not in ctx.problem.tasks:
            continue
        duration = ctx.problem.tasks[task.id].duration
        row: dict[str, Any] = {**_named(task.id, task.label), "duration": duration}
        t = timings.get(task.id)
        if t is not None:
            row["time"] = _span(t.start, t.end - t.start)
        if status.get(task.id, "on_track") != "on_track":
            row["status"] = status[task.id]
        if task.requirements:
            row["needs"] = [r.skill for r in task.requirements]
        if t is not None and t.assignments:
            row["assigned"] = t.assignments
        if task.id in after:
            row["after"] = after[task.id]
        if task.min_duration is not None:
            row["can_shorten_to"] = task.min_duration
        if task.helper is not None:
            row["helper"] = {
                "shortens_to": task.helper.duration,
                "qualified": [r.id for r in sc.resources if task.helper.skill in r.skills],
            }
        if task.optional:
            row["optional"] = True
        if task.deadline is not None:
            row["deadline"] = fmt_clock(task.deadline)
        rows.append(row)
    return rows


def _resource_rows(ctx: AgentContext) -> list[dict[str, Any]]:
    rows = []
    for r in ctx.scenario.resources:
        row: dict[str, Any] = {
            **_named(r.id, r.label),
            "skills": list(r.skills),
            "available": f"{fmt_clock(r.available.start)}-{fmt_clock(r.available.end)}",
        }
        blocked = ctx.problem.resources[r.id].blocked if r.id in ctx.problem.resources else ()
        if blocked:
            row["blocked"] = [f"{fmt_clock(w.start)}-{fmt_clock(w.end)}" for w in blocked]
        if r.standby and r.id not in ctx.problem.activated:
            row["standby"] = True
        rows.append(row)
    return rows


def _playbook_view(ctx: AgentContext, c: Candidate) -> dict[str, Any]:
    """A server-verified option, compared on the same measures as the model's own verified results."""
    view = {"candidate_id": c.id, "what": c.rationale, **_evaluation_view(c.evaluation)}
    del view["status"]  # always verified: playbook options are registered only after verification
    view["tasks_changed_vs_doing_nothing"] = len(touched_tasks(c.evaluation, ctx.do_nothing))
    return view


def _situation(ctx: AgentContext) -> dict[str, Any]:
    """The disrupted plan, as facts only. Coordinator preferences are in the user message, not repeated here."""
    sc, impact = ctx.scenario, ctx.impact
    timings = {t.task_id: t for t in impact.timings}
    sched = impact.schedule
    out: dict[str, Any] = {
        "deadline": fmt_clock(sched.deadline),
        "doors_ready_if_nobody_acts": fmt_clock(sched.readiness) if sched.readiness is not None else "never (blocked)",
        "minutes_late": sched.deadline_delta,
    }
    if NO_CHANGE_ID in ctx.candidates:
        out["no_change_candidate"] = NO_CHANGE_ID
    out["disruptions"] = [_shock_text(sc, s) for s in ctx.revision.state.shocks]
    # "task HH:MM: why it cannot start earlier", in chain order.
    out["driving_path"] = [
        f"{tid} {fmt_clock(timings[tid].start)}: {timings[tid].binding.text}"
        for tid in sched.driving_path
        if tid in timings
    ]
    if ctx.revision.state.committed.actions:
        out["already_applied"] = [a.model_dump() for a in ctx.revision.state.committed.actions]
    out["tasks"] = _task_rows(ctx)
    out["resources"] = _resource_rows(ctx)
    out["idle_people_during_critical_chain"] = idle_people(ctx)
    out["verified_playbook_options"] = [
        _playbook_view(ctx, c) for c in ctx.candidates.values() if c.origin == "playbook"
    ]
    return out | progress_facts(ctx)


def _inspect(ctx: AgentContext, args: InspectTaskArgs) -> ToolOutcome:
    if args.task_id not in ctx.problem.tasks:
        return ToolOutcome(
            {"error": f"unknown task_id {args.task_id!r}"}, "diagnose", f"unknown task {args.task_id}", ok=False
        )
    task = ctx.scenario.task(args.task_id)
    timing = next((t for t in ctx.impact.timings if t.task_id == args.task_id), None)
    eligible = {
        req.id: [
            {"id": r.id, "label": r.label, "standby": r.standby and r.id not in ctx.problem.activated}
            for r in ctx.scenario.resources
            if req.skill in r.skills
        ]
        for req in task.requirements
    }
    content: dict[str, Any] = {
        "id": task.id,
        "label": task.label,
        "release": fmt_clock(ctx.problem.tasks[task.id].release),
        "requirements": {r.id: r.skill for r in task.requirements},
        "eligible_resources": eligible,
        "predecessors": [d.from_id for d in ctx.problem.dependencies if d.to_id == task.id],
        "successors": [d.to_id for d in ctx.problem.dependencies if d.from_id == task.id],
    }
    if timing is not None:
        content |= {
            "start": fmt_clock(timing.start),
            "end": fmt_clock(timing.end),
            "slack_minutes": timing.slack,
            "why_not_earlier": timing.binding.text,
            "constraint_id": timing.binding.constraint_id,
        }
    return ToolOutcome(content, "diagnose", f"{task.label}: {content.get('why_not_earlier', 'not scheduled')}", ok=True)


def _menu(ctx: AgentContext) -> ToolOutcome:
    content = {
        "menu": [
            {
                "label": m.label,
                "actions": [a.model_dump() for a in m.actions],
                "cost": m.cost_hint,
                "tradeoff": m.tradeoff,
            }
            for m in ctx.menu
        ],
        "free_form_rules": [
            "assign_resource {task_id, requirement_id, resource_id}: resource needs the skill and must be active"
            " (activate standby first).",
            "pin_start {task_id, start 'HH:MM'}: fix a start time to force a resequence (e.g. unload something earlier).",
            "add_helper {task_id, resource_id}: a second qualified person shortens a task that allows it; the helper"
            " is busy meanwhile, which can delay their other work.",
            "compress_task: any duration from the minimum to the nominal; guest impact scales with minutes cut,"
            " so cut only what is needed.",
            "Menu and free-form actions combine in one patch. Smaller patches are better.",
        ],
        "evaluations_remaining": ctx.max_evaluations - ctx.evaluations_used,
    }
    return ToolOutcome(content, "plan", f"{len(ctx.menu)} permitted interventions", ok=True)


def preferences_view(prefs: Preferences) -> dict[str, Any]:
    view: dict[str, Any] = {
        "note": "Soft preferences: they rank verified options, they never override hard constraints.",
        "guest_experience": prefs.guest_experience,
        "spend": prefs.spend,
        "crew_stability": prefs.crew_stability,
    }
    if prefs.budget_cap_cents is not None:
        view["budget_cap_eur"] = prefs.budget_cap_cents / 100
    if prefs.min_margin_minutes:
        view["min_spare_minutes"] = prefs.min_margin_minutes
    if prefs.protected_tasks:
        view["protected_tasks"] = list(prefs.protected_tasks)
    return view


def idle_people(ctx: AgentContext) -> list[dict[str, Any]]:
    """People with free time while the doors-setting chain runs, and how they could help it.

    Facts from the do-nothing plan only; the model decides whether using them is wise and the
    verifier decides whether it works.
    """
    scenario, problem = ctx.scenario, ctx.problem
    plan = ctx.do_nothing.by_task()
    chain = [t for t in ctx.impact.schedule.driving_path if t in plan and not problem.tasks[t].milestone]
    if not chain:
        return []
    window_start = min(plan[t].start for t in chain)
    window_end = max(plan[t].start + problem.tasks[t].duration for t in chain)
    out: list[dict[str, Any]] = []
    for res in scenario.resources:
        if res.kind != "person" or res.id not in problem.resources:
            continue
        eff = problem.resources[res.id]
        busy = sorted(
            (e.start, e.start + problem.tasks[e.task_id].duration)
            for e in ctx.do_nothing.entries
            if res.id in e.assignments.values() and problem.tasks[e.task_id].duration > 0
        )
        busy += [(w.start, w.end) for w in eff.blocked]
        busy.sort()
        free: list[tuple[int, int]] = []
        cursor = max(window_start, eff.available.start)
        for start, end in busy:
            if start > cursor:
                free.append((cursor, min(start, window_end)))
            cursor = max(cursor, end)
        if cursor < min(window_end, eff.available.end):
            free.append((cursor, min(window_end, eff.available.end)))
        free = [(a, b) for a, b in free if b - a >= IDLE_MIN_MINUTES]
        if not free:
            continue
        could_help = []
        for tid in chain:
            task = scenario.task(tid)
            span = (plan[tid].start, plan[tid].start + problem.tasks[tid].duration)
            overlaps = any(a < span[1] and span[0] < b for a, b in free)
            if not overlaps:
                continue
            if task.helper is not None and task.helper.skill in res.skills:
                could_help.append({"task": tid, "as": "helper (add_helper)", "shortens_to": task.helper.duration})
            elif any(req.skill in res.skills for req in task.requirements):
                could_help.append({"task": tid, "as": "qualified to do it"})
        row: dict[str, Any] = {"person": res.id, "free": [f"{fmt_clock(a)}-{fmt_clock(b)}" for a, b in free]}
        if could_help:
            row["could_help_on_chain"] = could_help
        out.append(row)
    return out


def progress_facts(ctx: AgentContext) -> dict[str, Any]:
    """Coverage gaps and untried combinations, computed only from the model's own candidates."""
    mine = [(c.id, c.evaluation) for c in ctx.candidates.values() if c.origin == "model"]
    server = [(c.id, c.evaluation) for c in ctx.candidates.values() if c.origin != "model"]
    out: dict[str, Any] = {}
    cov = coverage(mine, server, ctx.preferences, ctx.do_nothing)
    if cov is not None:
        out["coverage_of_your_verified_options"] = cov
    combos = combinable_partials(mine, ctx.impact.schedule.readiness)
    if combos:
        out["combinable_partial_fixes"] = {"groups": combos}
    return out


def _evaluation_view(ev: Evaluation) -> dict[str, Any]:
    out: dict[str, Any] = {"status": ev.status.value}
    if ev.schedule is not None and ev.schedule.readiness is not None:
        out["doors_ready"] = fmt_clock(ev.schedule.readiness)
        out["minutes_before_deadline"] = -(ev.schedule.deadline_delta or 0)
    if ev.status == EvaluationStatus.VERIFIED:
        out |= {
            "cost_eur": ev.cost_cents / 100,
            "service_impacts": [s.text for s in ev.service_impacts],
            "disruption_minutes": ev.disruption_minutes,
            "reassignments": ev.reassignments,
        }
    if ev.violations:
        out["violations"] = [{"constraint": v.constraint_id, "message": v.message} for v in ev.violations]
    if ev.infeasibility is not None:
        out["why_infeasible"] = ev.infeasibility.reasons
        if ev.infeasibility.best_readiness is not None:
            out["best_possible_readiness_with_this_patch"] = fmt_clock(ev.infeasibility.best_readiness)
    if ev.status == EvaluationStatus.UNKNOWN:
        out["note"] = "Solver timed out without proof. Treat as not verified."
    return out


def _evaluate(ctx: AgentContext, args: EvaluatePatchArgs) -> ToolOutcome:
    if ctx.evaluations_used >= ctx.max_evaluations:
        return ToolOutcome(
            {"error": "evaluation budget exhausted; call submit_options now"}, "verify", "budget exhausted", ok=False
        )
    ctx.evaluations_used += 1
    patch = Patch(actions=tuple(args.actions), rationale=args.rationale)
    state = ctx.revision.state
    ev = evaluate_patch(ctx.scenario, state.shocks, state.committed, patch, state.plan)
    phase: Phase = "revise" if ctx.rejected_or_infeasible > 0 else "verify"
    cid = f"c{ctx.evaluations_used}"
    candidate = Candidate(id=cid, evaluation=ev, rationale=args.rationale)
    ctx.candidates[cid] = candidate
    if ev.status != EvaluationStatus.VERIFIED:
        ctx.rejected_or_infeasible += 1
    content = {
        "candidate_id": cid,
        **_evaluation_view(ev),
        "evaluations_remaining": ctx.max_evaluations - ctx.evaluations_used,
    }
    no_action = ctx.impact.schedule.readiness
    best = ev.infeasibility.best_readiness if ev.infeasibility is not None else None
    if best is not None and no_action is not None:
        content["minutes_gained_vs_doing_nothing"] = no_action - best
    if ev.status == EvaluationStatus.VERIFIED:
        touched = touched_tasks(ev, ctx.do_nothing)
        report = assess(ev, ctx.preferences, len(touched))
        content["preference_check"] = {
            "breaches": [b.text for b in report.breaches],
            "penalty_points": report.total_points,
            "tasks_changed_vs_doing_nothing": len(touched),
        }
    content |= progress_facts(ctx)
    summary = f"{cid}: {ev.status.value}"
    if "doors_ready" in content:
        summary += f", doors ready {content['doors_ready']}"
    return ToolOutcome(content, phase, summary, ok=True, candidate=candidate)


def _submit(ctx: AgentContext, args: SubmitOptionsArgs) -> ToolOutcome:
    bad = [
        o.candidate_id
        for o in args.options
        if o.candidate_id not in ctx.candidates
        or ctx.candidates[o.candidate_id].evaluation.status != EvaluationStatus.VERIFIED
    ]
    if bad:
        return ToolOutcome(
            {"error": f"only verified candidate ids can be submitted; not verified: {bad}"},
            "present",
            "submission rejected: unverified candidates",
            ok=False,
        )
    if len({o.candidate_id for o in args.options}) != len(args.options):
        return ToolOutcome({"error": "duplicate candidate ids"}, "present", "submission rejected: duplicates", ok=False)
    ctx.submitted = args
    return ToolOutcome(
        {"accepted": True}, "present", f"{len(args.options)} option(s) submitted", ok=True, terminal=True
    )


_ARGS: dict[str, type[Strict]] = {
    TOOL_GET_SITUATION: NoArgs,
    TOOL_INSPECT_TASK: InspectTaskArgs,
    TOOL_LIST_INTERVENTIONS: NoArgs,
    TOOL_EVALUATE_PATCH: EvaluatePatchArgs,
    TOOL_SUBMIT_OPTIONS: SubmitOptionsArgs,
}


def execute_tool(ctx: AgentContext, name: str, raw_arguments: str) -> ToolOutcome:
    model = _ARGS.get(name)
    if model is None:
        return ToolOutcome(
            {"error": f"unknown tool {name[:48]!r}"}, "diagnose", f"rejected unknown tool {name[:48]!r}", ok=False
        )
    try:
        parsed_json = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        return ToolOutcome(
            {"error": "arguments were not valid JSON"}, "diagnose", f"{name}: invalid JSON arguments", ok=False
        )
    try:
        args = model.model_validate(_clean_actions(parsed_json))
    except ValidationError as exc:
        errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:6]]
        return ToolOutcome(
            {"error": "invalid arguments", "details": errors}, "diagnose", f"{name}: invalid arguments", ok=False
        )

    if isinstance(args, InspectTaskArgs):
        return _inspect(ctx, args)
    if isinstance(args, EvaluatePatchArgs):
        return _evaluate(ctx, args)
    if isinstance(args, SubmitOptionsArgs):
        return _submit(ctx, args)
    if name == TOOL_LIST_INTERVENTIONS:
        return _menu(ctx)
    situation = _situation(ctx)
    return ToolOutcome(
        situation,
        "perceive",
        f"doors ready {situation['doors_ready_if_nobody_acts']} vs deadline {situation['deadline']}",
        ok=True,
    )
