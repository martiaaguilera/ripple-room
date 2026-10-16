"""Server-side inference budget and emergency kill switch.

This bounds what *this process* will spend on model calls per UTC day. It is an
application-side control, not a provider-side spending cap: Vercel may run more
than one instance, each with its own counters, and a restart resets them. The
real worst case is therefore (instances x daily budget); see docs/operations.md.
"""

from __future__ import annotations

import datetime as dt
import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

AiStatus = Literal["live", "mock", "paused", "budget_exhausted", "unconfigured"]


@dataclass(frozen=True)
class BudgetLimits:
    daily_tokens: int
    daily_runs: int
    per_ip_daily_runs: int


class InferenceBudget:
    def __init__(self, limits: BudgetLimits) -> None:
        self._limits = limits
        self._lock = threading.Lock()
        self._day = ""
        self._tokens = 0
        self._runs = 0
        self._per_ip: dict[str, int] = defaultdict(int)

    def _roll(self) -> None:
        today = dt.datetime.now(dt.UTC).date().isoformat()
        if today != self._day:
            self._day = today
            self._tokens = 0
            self._runs = 0
            self._per_ip.clear()

    def exhausted(self) -> bool:
        with self._lock:
            self._roll()
            return self._tokens >= self._limits.daily_tokens or self._runs >= self._limits.daily_runs

    def try_start(self, client: str) -> str | None:
        """Reserve one model-backed request; returns a refusal reason or None."""
        with self._lock:
            self._roll()
            if self._tokens >= self._limits.daily_tokens or self._runs >= self._limits.daily_runs:
                return "budget"
            if self._per_ip[client] >= self._limits.per_ip_daily_runs:
                return "client"
            self._runs += 1
            self._per_ip[client] += 1
            if len(self._per_ip) > 50_000:  # bound memory under abuse
                self._per_ip.clear()
            return None

    def record_tokens(self, tokens: int) -> None:
        with self._lock:
            self._roll()
            self._tokens += max(0, tokens)

    def snapshot(self) -> dict[str, int | str]:
        with self._lock:
            self._roll()
            return {"day": self._day, "tokens": self._tokens, "runs": self._runs}
