"""Globally shared, atomic inference quota (optional; fail-closed when required).

Each live model-backed request first *reserves* its worst-case token cost in a shared
store, atomically refusing when the daily or lifetime budget would be exceeded, and
refunds the unused part afterwards. Reservations of crashed requests are never
refunded, so errors overcount spend rather than undercount it.

Backend: Upstash Redis over its REST API (free tier, no card), reached with the
httpx client the project already uses. The Lua script runs atomically in Redis.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

# KEYS[1] daily counter, KEYS[2] lifetime counter
# ARGV[1] tokens to reserve, ARGV[2] daily budget, ARGV[3] lifetime budget, ARGV[4] daily TTL seconds
RESERVE_SCRIPT = """
local day = redis.call('INCRBY', KEYS[1], ARGV[1])
if day == tonumber(ARGV[1]) then redis.call('EXPIRE', KEYS[1], ARGV[4]) end
local total = redis.call('INCRBY', KEYS[2], ARGV[1])
if day > tonumber(ARGV[2]) or total > tonumber(ARGV[3]) then
  redis.call('DECRBY', KEYS[1], ARGV[1])
  redis.call('DECRBY', KEYS[2], ARGV[1])
  return -1
end
return day
"""

DAILY_TTL_SECONDS = 2 * 24 * 3600


class QuotaUnavailableError(RuntimeError):
    """The shared quota could not be checked; callers must fail closed."""


@dataclass(frozen=True)
class Reservation:
    tokens: int
    day: str


class GlobalQuota(Protocol):
    def reserve(self, tokens: int) -> Reservation | None:
        """Atomically reserve tokens; None means the budget would be exceeded."""
        ...

    def refund(self, reservation: Reservation, used: int) -> None:
        """Give back the unused part of a reservation (best effort)."""
        ...

    def usage(self) -> dict[str, int]: ...


class UpstashQuota:
    def __init__(
        self,
        *,
        url: str,
        token: str,
        daily_budget: int,
        lifetime_budget: int,
        prefix: str = "rr:ai",
        timeout: float = 3.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not url or not token:
            raise QuotaUnavailableError("Upstash URL or token missing.")
        self._url = url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._daily = daily_budget
        self._lifetime = lifetime_budget
        self._prefix = prefix
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def _keys(self, day: str) -> tuple[str, str]:
        return f"{self._prefix}:tokens:{day}", f"{self._prefix}:tokens:total"

    def _command(self, *args: str | int) -> Any:
        try:
            res = self._client.post(self._url, json=[str(a) for a in args], headers=self._headers)
            res.raise_for_status()
            body = res.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise QuotaUnavailableError(f"Quota store unreachable: {type(exc).__name__}") from exc
        if not isinstance(body, dict) or "error" in body or "result" not in body:
            raise QuotaUnavailableError("Quota store returned an error.")
        return body["result"]

    def reserve(self, tokens: int) -> Reservation | None:
        day = dt.datetime.now(dt.UTC).date().isoformat()
        daily_key, total_key = self._keys(day)
        result = self._command(
            "EVAL", RESERVE_SCRIPT, 2, daily_key, total_key, tokens, self._daily, self._lifetime, DAILY_TTL_SECONDS
        )
        try:
            granted = int(result) >= 0
        except (TypeError, ValueError) as exc:
            raise QuotaUnavailableError("Unexpected quota response.") from exc
        return Reservation(tokens=tokens, day=day) if granted else None

    def refund(self, reservation: Reservation, used: int) -> None:
        unused = max(0, reservation.tokens - max(0, used))
        if unused == 0:
            return
        daily_key, total_key = self._keys(reservation.day)
        try:
            self._command("DECRBY", daily_key, unused)
            self._command("DECRBY", total_key, unused)
        except QuotaUnavailableError:
            pass  # failing to refund only overcounts spend; never undercounts

    def usage(self) -> dict[str, int]:
        daily_key, total_key = self._keys(dt.datetime.now(dt.UTC).date().isoformat())
        day = self._command("GET", daily_key)
        total = self._command("GET", total_key)
        return {
            "today": int(day or 0),
            "total": int(total or 0),
            "daily_budget": self._daily,
            "lifetime_budget": self._lifetime,
        }
