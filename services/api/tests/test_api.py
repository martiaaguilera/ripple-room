"""HTTP contract tests for the stateless API."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def _demo(client: TestClient) -> dict[str, Any]:
    res = client.get("/api/demo")
    assert res.status_code == 200
    return res.json()


def _shock(client: TestClient, revision: dict[str, Any], preset_id: str) -> dict[str, Any]:
    res = client.post("/api/shock", json={"revision": revision, "preset_id": preset_id})
    assert res.status_code == 200, res.text
    return res.json()


def test_health_reports_mode_without_secrets(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["ai"]["mode"] in ("live", "mock")
    assert "key" not in str(body).lower()


def test_demo_starts_verified(client: TestClient) -> None:
    demo = _demo(client)
    initial = demo["initial"]
    assert initial["verified"] is True
    assert initial["impact"] is None
    assert initial["plan_view"]["schedule"]["readiness"] == 17 * 60 + 40
    assert initial["revision"]["id"].startswith("rev_")
    assert {p["id"] for p in demo["presets"]} >= {"truck-delay-35", "truck-breakdown-90"}


def test_shock_creates_new_immutable_revision_with_impact(client: TestClient) -> None:
    demo = _demo(client)
    base = demo["initial"]["revision"]
    shocked = _shock(client, base, "truck-delay-35")
    assert shocked["revision"]["id"] != base["id"]
    assert shocked["revision"]["state"]["parent_id"] == base["id"]
    assert shocked["verified"] is False
    statuses = {t["task_id"]: t["status"] for t in shocked["impact"]["tasks"]}
    assert statuses["doors-open"] == "breach"
    # Same input, same revision id (content addressed).
    again = _shock(client, base, "truck-delay-35")
    assert again["revision"]["id"] == shocked["revision"]["id"]


def test_tampered_revision_rejected(client: TestClient) -> None:
    rev = _demo(client)["initial"]["revision"]
    rev["state"]["plan"]["entries"][0]["start"] = 0
    res = client.post("/api/view", json={"revision": rev})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_REVISION"


@pytest.mark.parametrize(
    "payload",
    [
        {"preset_id": "nope"},
        {"shock": {"kind": "task_delay", "task_id": "ghost", "delay_minutes": 10}},
        {"shock": {"kind": "task_delay", "task_id": "truck-arrival", "delay_minutes": 9999}},
        {"shock": {"kind": "meteor", "task_id": "truck-arrival"}},
        {},
    ],
)
def test_invalid_shocks_rejected(client: TestClient, payload: dict[str, Any]) -> None:
    rev = _demo(client)["initial"]["revision"]
    res = client.post("/api/shock", json={"revision": rev, **payload})
    assert res.status_code == 422
    assert res.json()["error"]["code"] in ("INVALID_SHOCK", "VALIDATION_ERROR")


def test_shock_limit(client: TestClient) -> None:
    rev = _demo(client)["initial"]["revision"]
    for _ in range(4):
        rev = _shock(client, rev, "dock-delay-20")["revision"]
    res = client.post("/api/shock", json={"revision": rev, "preset_id": "dock-delay-20"})
    assert res.status_code == 422


def test_evaluate_search_apply_round_trip(client: TestClient) -> None:
    rev = _shock(client, _demo(client)["initial"]["revision"], "truck-delay-35")["revision"]
    search = client.post("/api/search", json={"revision": rev}).json()
    assert search["source"] == "deterministic-search"
    assert search["base_revision_id"] == rev["id"]
    assert len(search["options"]) >= 1
    option = search["options"][0]["evaluation"]
    assert option["status"] == "verified"

    applied = client.post(
        "/api/apply",
        json={"revision": rev, "base_revision_id": rev["id"], "patch": option["patch"], "plan": option["plan"]},
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["verified"] is True
    assert body["plan_view"]["schedule"]["deadline_delta"] <= 0
    assert body["revision"]["state"]["parent_id"] == rev["id"]
    assert body["revision"]["state"]["source"] == "apply"


def test_apply_rejects_stale_revision(client: TestClient) -> None:
    rev = _shock(client, _demo(client)["initial"]["revision"], "truck-delay-35")["revision"]
    option = client.post("/api/search", json={"revision": rev}).json()["options"][0]["evaluation"]
    res = client.post(
        "/api/apply",
        json={
            "revision": rev,
            "base_revision_id": "rev_0000000000000000",
            "patch": option["patch"],
            "plan": option["plan"],
        },
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "STALE_REVISION"


def test_apply_rejects_plan_that_violates_constraints(client: TestClient) -> None:
    rev = _shock(client, _demo(client)["initial"]["revision"], "truck-delay-35")["revision"]
    # The pre-shock plan no longer holds: applying it unchanged must fail verification.
    res = client.post(
        "/api/apply",
        json={"revision": rev, "base_revision_id": rev["id"], "patch": {"actions": []}, "plan": rev["state"]["plan"]},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PLAN_INVALID"


def test_evaluate_reports_rejection_for_malformed_patch(client: TestClient) -> None:
    rev = _shock(client, _demo(client)["initial"]["revision"], "truck-delay-35")["revision"]
    res = client.post(
        "/api/evaluate",
        json={"revision": rev, "patch": {"actions": [{"type": "defer_task", "task_id": "soundcheck"}]}},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"


def test_evaluate_rejects_unknown_action_types(client: TestClient) -> None:
    rev = _demo(client)["initial"]["revision"]
    res = client.post("/api/evaluate", json={"revision": rev, "patch": {"actions": [{"type": "exec", "cmd": "ls"}]}})
    assert res.status_code == 422


def test_impossible_case_search_is_empty(client: TestClient) -> None:
    rev = _shock(client, _demo(client)["initial"]["revision"], "truck-breakdown-90")["revision"]
    search = client.post("/api/search", json={"revision": rev}).json()
    assert search["options"] == []
