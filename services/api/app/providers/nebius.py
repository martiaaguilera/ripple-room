"""Nebius Token Factory adapter (OpenAI-compatible chat completions over HTTPS).

Server-side only. The API key is read from settings and sent solely in the
Authorization header; it is never logged or echoed. Retries are bounded and
only for transient failures (429, 5xx, timeouts) with jittered backoff.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from typing import Any

import httpx

from app.providers.base import ChatResult, Message, ProviderError, ToolCall, ToolSpec, Usage

log = logging.getLogger("ripple.nebius")

_REQUEST_ID_HEADERS = ("x-request-id", "request-id", "x-nebius-request-id", "cf-ray")


class NebiusProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 45.0,
        max_retries: int = 2,
        extra_body: dict[str, Any] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("MODEL_UNAVAILABLE", "Nebius API key is not configured.")
        self._api_key = api_key
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._model = model
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._extra_body = extra_body or {}
        self._transport = transport

    @property
    def name(self) -> str:
        return "nebius-token-factory"

    @property
    def model(self) -> str:
        return self._model

    @property
    def live(self) -> bool:
        return True

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSpec] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.6,
    ) -> ChatResult:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": 0.95,
            **self._extra_body,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

        attempt = 0
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            while True:
                t0 = time.perf_counter()
                try:
                    response = await client.post(self._url, json=body, headers=headers)
                except httpx.TimeoutException as exc:
                    error = ProviderError("MODEL_TIMEOUT", "Nebius request timed out.", retryable=True)
                    error.__cause__ = exc
                except httpx.HTTPError as exc:
                    error = ProviderError(
                        "MODEL_UNAVAILABLE", f"Network error contacting Nebius: {type(exc).__name__}", retryable=True
                    )
                    error.__cause__ = exc
                else:
                    latency_ms = round((time.perf_counter() - t0) * 1000)
                    if response.status_code == 200:
                        return self._parse(response, latency_ms)
                    error = self._classify(response)
                if not error.retryable or attempt >= self._max_retries:
                    raise error
                attempt += 1
                delay = min(8.0, 0.75 * 2**attempt) * (0.5 + random.random())  # noqa: S311 - jitter, not crypto
                log.warning("nebius retry attempt=%d code=%s delay=%.2fs", attempt, error.code, delay)
                await asyncio.sleep(delay)

    @staticmethod
    def _classify(response: httpx.Response) -> ProviderError:
        status = response.status_code
        text = response.text[:300].lower()
        if status in (401, 403):
            return ProviderError("MODEL_UNAVAILABLE", "Nebius rejected the credentials.", status=status)
        if status == 402 or "insufficient" in text or "credit" in text or "balance" in text:
            return ProviderError("CREDIT_EXHAUSTED", "Nebius account has insufficient credits.", status=status)
        if status == 404:
            return ProviderError("MODEL_UNAVAILABLE", "Model not found on Nebius (check model id).", status=status)
        if status == 429:
            return ProviderError("RATE_LIMITED", "Nebius rate limit reached.", status=status, retryable=True)
        if status >= 500:
            return ProviderError("MODEL_UNAVAILABLE", f"Nebius server error {status}.", status=status, retryable=True)
        return ProviderError("BAD_RESPONSE", f"Nebius returned HTTP {status}.", status=status)

    def _parse(self, response: httpx.Response, latency_ms: int) -> ChatResult:
        try:
            payload = response.json()
            choice = payload["choices"][0]
            message: dict[str, Any] = choice["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("BAD_RESPONSE", "Malformed completion payload from Nebius.") from exc
        calls = [
            ToolCall(
                id=str(c.get("id") or f"call_{i}"),
                name=str(c["function"]["name"]),
                arguments=str(c["function"].get("arguments") or "{}"),
            )
            for i, c in enumerate(message.get("tool_calls") or [])
            if isinstance(c, dict) and isinstance(c.get("function"), dict) and "name" in c["function"]
        ]
        usage_raw = payload.get("usage") or {}
        usage = Usage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
            completion_tokens=int(usage_raw.get("completion_tokens") or 0),
            total_tokens=int(usage_raw.get("total_tokens") or 0),
        )
        request_id = next(
            (response.headers[h] for h in _REQUEST_ID_HEADERS if h in response.headers), None
        ) or payload.get("id")
        reasoning = message.get("reasoning_content") or message.get("reasoning")
        echo: Message = {"role": "assistant", "content": message.get("content") or ""}
        if calls:
            echo["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}} for c in calls
            ]
        log.info(
            "nebius completion model=%s request_id=%s latency_ms=%d prompt=%d completion=%d tools=%s",
            payload.get("model", self._model),
            request_id,
            latency_ms,
            usage.prompt_tokens,
            usage.completion_tokens,
            json.dumps([c.name for c in calls]),
        )
        return ChatResult(
            model=str(payload.get("model") or self._model),
            content=message.get("content"),
            reasoning=str(reasoning) if reasoning else None,
            tool_calls=calls,
            finish_reason=choice.get("finish_reason"),
            usage=usage,
            latency_ms=latency_ms,
            request_id=str(request_id) if request_id else None,
            raw_message=echo,
        )
