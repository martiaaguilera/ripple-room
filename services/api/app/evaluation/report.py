"""Aggregate case results into a transparent Markdown report (no hand-edited numbers)."""

from __future__ import annotations

from collections.abc import Sequence
from statistics import mean, median

from app.evaluation.harness import CaseResult, MethodResult

METHODS = ("agent", "playbook_search", "greedy", "oracle")


def _quality(m: MethodResult, oracle: MethodResult) -> str:
    """Compare a method's best option with the oracle's under the same preference ranking."""
    if not oracle.found:
        return "correct: none" if not m.found else "INVALID"
    if not m.found:
        return "missed"
    assert m.best is not None and oracle.best is not None  # noqa: S101
    gap = len(m.best.breaches) - len(oracle.best.breaches)
    if gap > 0:
        return f"+{gap} breach"
    regret = round(m.best.penalty - oracle.best.penalty, 1)
    return "optimal" if regret <= 0 else f"regret {regret}"


def summarize(results: Sequence[CaseResult], meta: dict[str, object]) -> str:
    lines = ["# Evaluation results", ""]
    lines += [f"- {k}: {v}" for k, v in meta.items()]
    lines += ["", "## Summary", "", "| Metric | " + " | ".join(METHODS) + " |", "|---|" + "---|" * len(METHODS)]
    feasible_cases = [r for r in results if r.methods["oracle"].found]

    def row(name: str, fn) -> None:  # type: ignore[no-untyped-def]
        cells = []
        for method in METHODS:
            vals = [r.methods[method] for r in results if method in r.methods]
            cells.append(fn(vals, method) if vals else "n/a")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    row("Cases run", lambda v, _m: str(len(v)))
    row(
        "Found a verified recovery when one exists",
        lambda v, m: f"{sum(1 for r in feasible_cases if m in r.methods and r.methods[m].found)}/{len(feasible_cases)}",
    )
    row(
        "Reported 'none' correctly when none exists",
        lambda v, m: (
            f"{sum(1 for r in results if not r.methods['oracle'].found and m in r.methods and not r.methods[m].found)}/{len(results) - len(feasible_cases)}"
        ),
    )
    row("Options failing independent re-validation", lambda v, _m: str(sum(x.invalid_options for x in v)))
    row(
        "Best option matches oracle (breaches and penalty)",
        lambda v, m: (
            f"{sum(1 for r in feasible_cases if m in r.methods and _quality(r.methods[m], r.methods['oracle']) == 'optimal')}/{len(feasible_cases)}"
        ),
    )
    row(
        "Best option has more preference breaches than oracle",
        lambda v, m: str(
            sum(1 for r in feasible_cases if m in r.methods and "breach" in _quality(r.methods[m], r.methods["oracle"]))
        ),
    )
    row("Median latency (ms)", lambda v, _m: f"{median(x.elapsed_ms for x in v):.0f}")
    row("Solver evaluations (mean)", lambda v, _m: f"{mean(x.solver_evaluations for x in v):.1f}")
    row("Model calls (mean)", lambda v, m: f"{mean(x.model_calls for x in v):.1f}" if m == "agent" else "–")
    row(
        "Tokens (mean)",
        lambda v, m: f"{mean(x.prompt_tokens + x.completion_tokens for x in v):.0f}" if m == "agent" else "–",
    )
    row("Cost USD (total)", lambda v, m: f"{sum(x.cost_usd for x in v):.4f}" if m == "agent" else "0")
    row(
        "Candidates the verifier did not accept (total)",
        lambda v, m: str(sum(x.rejected_candidates for x in v)) if m == "agent" else "–",
    )
    row(
        "Beyond-playbook actions tried (total)",
        lambda v, m: str(sum(x.beyond_playbook_actions for x in v)) if m == "agent" else "–",
    )

    def model_matches(r: CaseResult) -> bool:
        a, o = r.methods.get("agent"), r.methods["oracle"]
        if a is None or a.model_best is None or o.best is None:
            return False
        return len(a.model_best.breaches) <= len(o.best.breaches) and a.model_best.penalty <= o.best.penalty

    row(
        "System best comes from a model-proposed option",
        lambda v, m: (
            f"{sum(1 for x in v if x.best_origin == 'model')}/{sum(1 for x in v if x.best_origin)}"
            if m == "agent"
            else "–"
        ),
    )
    row(
        "Model-proposed option alone matches oracle",
        lambda v, m: (
            f"{sum(1 for r in feasible_cases if model_matches(r))}/{len(feasible_cases)}" if m == "agent" else "–"
        ),
    )
    row(
        "Model's own #1 = deterministic #1",
        lambda v, m: (
            f"{sum(1 for x in v if x.top_pick_agrees)}/{sum(1 for x in v if x.top_pick_agrees is not None)}"
            if m == "agent"
            else "–"
        ),
    )

    lines += [
        "",
        "## Per case",
        "",
        "| Case | Incident | Profile | Agent | Playbook search | Greedy | Oracle best | Agent calls / tokens / ms |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        o = r.methods["oracle"]
        best = (
            "none"
            if not o.found or o.best is None
            else f"€{o.best.cost_cents / 100:.0f}, {len(o.best.breaches)} breach, {o.best.penalty:.0f} pts"
        )
        a = r.methods.get("agent")
        agent_q = _quality(a, o) if a else "n/a"
        stats = f"{a.model_calls} / {a.prompt_tokens + a.completion_tokens} / {a.elapsed_ms}" if a else "–"
        lines.append(
            f"| {r.case_id} | {r.title} | {r.profile} | {agent_q} | {_quality(r.methods['playbook_search'], o)} | "
            f"{_quality(r.methods['greedy'], o)} | {best} | {stats} |"
        )
    failures = [
        r
        for r in results
        if "agent" in r.methods
        and (
            r.methods["agent"].error
            or _quality(r.methods["agent"], r.methods["oracle"]) not in ("optimal", "correct: none")
        )
    ]
    lines += ["", "## Agent shortfalls (not hidden)", ""]
    if not failures:
        lines.append("None in this run.")
    for r in failures:
        a = r.methods["agent"]
        lines.append(
            f"- **{r.case_id}** ({r.title}, {r.profile}): {_quality(a, r.methods['oracle'])}; stop={a.stop_reason}; error={a.error}"
        )
    return "\n".join(lines) + "\n"
