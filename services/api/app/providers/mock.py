"""Scripted, deterministic stand-in for the model. Development and CI only.

It is NOT intelligent and never claims to be: it walks the permitted menu in
order and submits whatever the verifier accepts. ``live`` is False and the UI
labels every run "Simulated agent (no model call)".
"""

from __future__ import annotations

import json
from typing import Any

from app.agent.tools import (
    TOOL_EVALUATE_PATCH,
    TOOL_GET_SITUATION,
    TOOL_LIST_INTERVENTIONS,
    TOOL_SUBMIT_OPTIONS,
)
from app.providers.base import ChatResult, Message, ToolCall, ToolSpec, Usage


class MockProvider:
    def __init__(self, max_evaluations: int = 4) -> None:
        self._max_evaluations = max_evaluations

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model(self) -> str:
        return "scripted-menu-walker"

    @property
    def live(self) -> bool:
        return False

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.6,
    ) -> ChatResult:
        del tools, max_tokens, temperature
        names: dict[str, str] = {}
        for m in messages:
            for c in m.get("tool_calls") or []:
                names[c["id"]] = c["function"]["name"]
        results: list[tuple[str, dict[str, Any]]] = [
            (names.get(m["tool_call_id"], "?"), json.loads(m["content"])) for m in messages if m.get("role") == "tool"
        ]
        called = [n for n, _ in results]
        step = len([m for m in messages if m.get("role") == "assistant"])

        if TOOL_GET_SITUATION not in called:
            return self._call(step, TOOL_GET_SITUATION, {})
        if TOOL_LIST_INTERVENTIONS not in called:
            return self._call(step, TOOL_LIST_INTERVENTIONS, {})

        menu = next(c for n, c in results if n == TOOL_LIST_INTERVENTIONS)["menu"]
        evaluations = [c for n, c in results if n == TOOL_EVALUATE_PATCH and "candidate_id" in c]
        verified = [e["candidate_id"] for e in evaluations if e.get("status") == "verified"]
        if len(evaluations) < min(self._max_evaluations, len(menu)) and len(verified) < 2:
            item = menu[len(evaluations)]
            return self._call(
                step,
                TOOL_EVALUATE_PATCH,
                {"actions": item["actions"], "rationale": f"Scripted trial of menu item: {item['label']}."},
            )
        options = [
            {
                "candidate_id": cid,
                "title": f"Scripted option {i + 1}",
                "why": "Verified by the constraint engine (scripted run).",
            }
            for i, cid in enumerate(verified[:3])
        ]
        return self._call(
            step, TOOL_SUBMIT_OPTIONS, {"options": options, "summary": "Scripted mock run: menu items tried in order."}
        )

    def _call(self, step: int, name: str, arguments: dict[str, Any]) -> ChatResult:
        call = ToolCall(id=f"mock_{step}", name=name, arguments=json.dumps(arguments))
        return ChatResult(
            model=self.model,
            content=None,
            reasoning=None,
            tool_calls=[call],
            finish_reason="tool_calls",
            usage=Usage(),
            latency_ms=0,
            request_id=None,
            raw_message={
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": call.id, "type": "function", "function": {"name": name, "arguments": call.arguments}}
                ],
            },
        )
