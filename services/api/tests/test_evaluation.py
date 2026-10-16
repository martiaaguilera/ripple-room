"""Evaluation harness and greedy baseline (deterministic parts + scripted agent)."""

from __future__ import annotations

from app.agent.runner import Budget
from app.domain.models import Patch, Scenario
from app.evaluation.cases import CASES
from app.evaluation.harness import CaseResult, run_agent_case, run_greedy, run_search
from app.evaluation.report import summarize
from app.fixtures import preset
from app.providers.mock import MockProvider
from app.solver.greedy import greedy_recovery


def test_twenty_unique_cases() -> None:
    assert len(CASES) == 20
    assert len({c.id for c in CASES}) == 20


def test_greedy_finds_trolley_for_truck_delay(scenario: Scenario) -> None:
    result = greedy_recovery(scenario, [preset("truck-delay-35").shock], Patch(), scenario.baseline)
    assert result.evaluation is not None
    assert result.steps == ["activate:trolley-2"]


def test_greedy_gives_up_honestly(scenario: Scenario) -> None:
    result = greedy_recovery(scenario, [preset("truck-breakdown-90").shock], Patch(), scenario.baseline)
    assert result.evaluation is None


async def test_harness_methods_agree_on_validity(scenario: Scenario) -> None:
    budget = Budget(max_model_calls=10, max_total_tokens=10_000, timeout_seconds=30, max_output_tokens=512)
    results = []
    for case in [c for c in CASES if c.id in ("c01", "c09", "c10")]:
        methods = {
            "oracle": run_search(scenario, case, oracle=True),
            "playbook_search": run_search(scenario, case, oracle=False),
            "greedy": run_greedy(scenario, case),
            "agent": await run_agent_case(scenario, case, MockProvider(max_evaluations=6), budget, 6, {}),
        }
        assert all(m.invalid_options == 0 for m in methods.values())
        results.append(CaseResult(case_id=case.id, title=case.title, profile=case.profile.id, methods=methods))
    by_id = {r.case_id: r for r in results}
    assert by_id["c10"].methods["oracle"].found is False
    assert by_id["c09"].methods["oracle"].found and not by_id["c09"].methods["playbook_search"].found
    report = summarize(results, {"agent_mode": "mock"})
    assert "Agent shortfalls" in report and "| c09 |" in report
