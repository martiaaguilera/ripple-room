"""Offline measurement of what one recovery run sends to the model (no model call, no tokenizer).

For each benchmark case it builds the same ``AgentContext`` the live agent gets and records the
character size of the fixed context (system prompt, user prompt, tool specs) and of the main tool
results, serialised exactly as the runner sends them (compact JSON). ``chars / 4`` is a rough,
tokenizer-free token estimate; it is used only to compare payload versions, never as a billed figure.

Run: ``uv run python -m app.evaluation.payload`` (prints a table; spends nothing).
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from typing import Any

from app.agent.prompts import SYSTEM_PROMPT, user_prompt
from app.agent.tools import (
    TOOL_EVALUATE_PATCH,
    TOOL_GET_SITUATION,
    TOOL_LIST_INTERVENTIONS,
    AgentContext,
    execute_tool,
    preferences_view,
    tool_content_json,
    tool_specs,
)
from app.domain.effective import compile_problem
from app.domain.models import Scenario
from app.evaluation.cases import CASES, Case
from app.evaluation.harness import case_revision

CHARS_PER_TOKEN = 4
MAX_EVALUATIONS = 6  # same verifier budget as the measured live runs
COMPONENTS = ("system", "user", "tools", "situation", "menu", "evaluate")


def compact(content: Any) -> str:
    """Serialise like ``run_agent`` does (``tool_content_json``), for any JSON value (e.g. the tool specs)."""
    return json.dumps(content, separators=(",", ":"), ensure_ascii=False)


def build_context(scenario: Scenario, case: Case) -> AgentContext:
    revision = case_revision(scenario, case)
    state = revision.state
    problem, _ = compile_problem(scenario, state.shocks, state.committed)
    assert problem is not None  # noqa: S101 - case shocks are fixture-validated
    return AgentContext.build(scenario, revision, problem, MAX_EVALUATIONS, case.profile.preferences)


@dataclass(frozen=True)
class CasePayload:
    case_id: str
    chars: dict[str, int]

    def tokens(self, component: str) -> int:
        return round(self.chars[component] / CHARS_PER_TOKEN)


def measure_case(scenario: Scenario, case: Case) -> CasePayload:
    """Sizes for one case. The "typical" evaluate_patch result is the first menu item's actions."""
    ctx = build_context(scenario, case)
    situation = execute_tool(ctx, TOOL_GET_SITUATION, "{}").content
    menu = execute_tool(ctx, TOOL_LIST_INTERVENTIONS, "{}").content
    first = menu["menu"][0]
    args = {"actions": first["actions"], "rationale": f"Try {first['label']}."}
    evaluated = execute_tool(ctx, TOOL_EVALUATE_PATCH, json.dumps(args)).content
    return CasePayload(
        case_id=case.id,
        chars={
            "system": len(SYSTEM_PROMPT),
            "user": len(user_prompt(case.profile.text, preferences_view(ctx.preferences))),
            "tools": len(compact(tool_specs())),
            "situation": len(tool_content_json(situation)),
            "menu": len(tool_content_json(menu)),
            "evaluate": len(tool_content_json(evaluated)),
        },
    )


def run_estimate_chars(p: CasePayload, model_calls: int = 7, evaluations: int = 4) -> int:
    """Approximate prompt characters billed over one run (each call re-sends the whole history).

    Shape of a typical measured run: call 1 sees the fixed context; get_situation and
    list_interventions results are re-sent on every later call; each evaluate_patch result is
    re-sent on every call after it. Assistant messages and model text are excluded (not ours to shrink).
    """
    c = p.chars
    fixed = c["system"] + c["user"] + c["tools"]
    total = fixed * model_calls
    total += c["situation"] * (model_calls - 1)  # appended after call 1
    total += c["menu"] * (model_calls - 2)  # appended after call 2
    for k in range(evaluations):  # evaluation k is appended after call 3 + k
        total += c["evaluate"] * max(model_calls - 3 - k, 0)
    return total


def measure_all(scenario: Scenario) -> list[CasePayload]:
    return [measure_case(scenario, case) for case in CASES]


def report(payloads: list[CasePayload]) -> str:
    lines = ["| component | mean chars | ~tokens (chars/4) | min | max |", "|---|---|---|---|---|"]
    for comp in COMPONENTS:
        values = [p.chars[comp] for p in payloads]
        mean = statistics.mean(values)
        lines.append(f"| {comp} | {mean:.0f} | {mean / CHARS_PER_TOKEN:.0f} | {min(values)} | {max(values)} |")
    runs = [run_estimate_chars(p) for p in payloads]
    mean_run = statistics.mean(runs)
    lines.append(
        f"| run estimate (7 calls, 4 evaluations) | {mean_run:.0f} | {mean_run / CHARS_PER_TOKEN:.0f} | "
        f"{min(runs)} | {max(runs)} |"
    )
    return "\n".join(lines)


def main() -> None:
    from app.fixtures import load_scenario

    print(report(measure_all(load_scenario())))


if __name__ == "__main__":
    main()
