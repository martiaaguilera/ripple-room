"""Best-effort, per-process limits for costly inference runs.

Serverless instances do not share memory, so this bounds each instance; the
per-run token/time caps and the provider-side spend limit bound the rest.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, per_minute: int) -> None:
        self._per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        window = self._hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self._per_minute:
            return False
        window.append(now)
        if len(self._hits) > 10_000:  # bound memory under abuse
            self._hits.clear()
        return True


class ConcurrencyGate:
    """Non-blocking cap on simultaneous runs (event-loop confined, so a plain counter is safe)."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._active = 0

    def try_acquire(self) -> bool:
        if self._active >= self._limit:
            return False
        self._active += 1
        return True

    def release(self) -> None:
        self._active = max(0, self._active - 1)
