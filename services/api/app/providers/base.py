"""Provider-neutral chat-completion interface used by the agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Message = dict[str, Any]
ToolSpec = dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text from the model; validated by the agent, never trusted


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class ChatResult:
    model: str
    content: str | None
    reasoning: str | None
    tool_calls: list[ToolCall]
    finish_reason: str | None
    usage: Usage
    latency_ms: int
    request_id: str | None = None
    raw_message: Message = field(default_factory=dict)  # assistant message to echo back into history


ProviderErrorCode = Literal["MODEL_UNAVAILABLE", "RATE_LIMITED", "CREDIT_EXHAUSTED", "MODEL_TIMEOUT", "BAD_RESPONSE"]


class ProviderError(Exception):
    def __init__(
        self, code: ProviderErrorCode, message: str, *, status: int | None = None, retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.retryable = retryable


class ChatProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def live(self) -> bool:
        """True only when responses come from a real remote model."""
        ...

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.6,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> ChatResult: ...
