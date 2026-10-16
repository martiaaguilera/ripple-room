"""Keyword-based stand-in for incident interpretation. Development/CI only.

It is deliberately simple and labelled ``mock`` end to end; it exists so the
confirm-before-apply flow can be tested without a model. It never runs in live mode.
"""

from __future__ import annotations

import re
from typing import Any

TOOL_REPORT_SITUATION = "report_situation"

_FENCE = re.compile(r"<<<\n(.*)\n>>>", re.S)
_MINUTES = re.compile(r"(\d{1,3})\s*(?:more\s+|extra\s+)?(?:min|minutes|mins)\b", re.I)
_WINDOW = re.compile(r"(\d{1,2}[:.]\d{2})\s*(?:-|–|to|until)\s*(\d{1,2}[:.]\d{2})", re.I)
_EURO = re.compile(r"(?:€|eur\s*)(\d{1,5})|(\d{1,5})\s*(?:€|eur|euros)\b", re.I)


def _text(message: str) -> str:
    match = _FENCE.search(message)
    return match.group(1) if match else message


def mock_interpretation(message: str) -> dict[str, Any]:
    text = _text(message)
    low = text.lower()
    incidents: list[dict[str, Any]] = []
    minutes = _MINUTES.search(text)
    if any(w in low for w in ("truck", "driver", "van", "delivery")) and minutes:
        incidents.append(
            {
                "kind": "task_delay",
                "task_id": "truck-arrival",
                "delay_minutes": int(minutes.group(1)),
                "evidence": "truck",
            }
        )
    elif "dock" in low and minutes:
        incidents.append(
            {"kind": "task_delay", "task_id": "dock-open", "delay_minutes": int(minutes.group(1)), "evidence": "dock"}
        )
    window = _WINDOW.search(text)
    if window and ("av" in low or "sound" in low or "audio" in low):
        incidents.append(
            {
                "kind": "resource_unavailable",
                "resource_id": "av-tech",
                "start": window.group(1).replace(".", ":"),
                "end": window.group(2).replace(".", ":"),
                "evidence": "AV",
            }
        )
    priorities: dict[str, Any] = {}
    if any(w in low for w in ("no spend", "zero", "cheap", "no extra", "no money")):
        priorities["spend"] = "protect"
    if any(w in low for w in ("guest", "experience", "sponsor", "audience")):
        priorities["guest_experience"] = "protect"
    euro = _EURO.search(text)
    if euro:
        priorities["budget_cap_eur"] = int(euro.group(1) or euro.group(2))
    if "vendor" in low and any(w in low for w in ("need", "keep", "protect", "sponsor")):
        priorities["protected_tasks"] = ["vendor-tables"]
    return {
        "incidents": incidents,
        "priorities": priorities,
        "unclear": []
        if incidents
        else ["No recognisable incident (mock interpreter understands truck/dock delays and AV absences only)."],
        "summary": "Keyword-based mock interpretation.",
    }
