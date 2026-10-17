"""Client identity for rate limiting."""

from __future__ import annotations

from fastapi import Request


def client_key(request: Request) -> str:
    """Client IP. Prefer headers the platform sets and clients cannot forge (on Vercel:
    x-vercel-forwarded-for / x-real-ip); the first x-forwarded-for entry is client-controlled,
    so fall back to the hop appended by the nearest proxy. Behind other hosts these headers
    may be forgeable; see docs/operations.md."""
    for header in ("x-vercel-forwarded-for", "x-real-ip"):
        value = request.headers.get(header, "").split(",")[0].strip()
        if value:
            return value[:64]
    forwarded = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if forwarded:
        return forwarded[-1][:64]
    return request.client.host if request.client else "unknown"
