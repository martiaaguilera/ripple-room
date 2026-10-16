"""Typed API errors. Every non-2xx response has the shape {"error": {code, message, details}}."""

from __future__ import annotations

from typing import Any, Literal

ErrorCode = Literal[
    "INVALID_SHOCK",
    "INVALID_REVISION",
    "STALE_REVISION",
    "PLAN_INVALID",
    "SOLVER_TIMEOUT",
    "MODEL_UNAVAILABLE",
    "AI_PAUSED",
    "AI_BUDGET_EXHAUSTED",
    "RATE_LIMITED",
    "CREDIT_EXHAUSTED",
    "BUSY",
    "VALIDATION_ERROR",
    "INTERNAL",
]


class ApiError(Exception):
    def __init__(self, status: int, code: ErrorCode, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details

    def payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}
