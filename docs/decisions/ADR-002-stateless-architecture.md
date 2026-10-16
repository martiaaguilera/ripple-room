# ADR-002 — Stateless, content-addressed API; Vercel-first deployment

- **Status:** Accepted (deployment target pending owner account + smoke deploy) · 2026-10-16
- **Context:** `docs/research/hosting.md`. Judges need free, unrestricted access through
  **15 Dec 2026**. Hugging Face Docker Spaces now require a paid plan; Koyeb, Cloud Run, Fly.io and
  Oracle need a card. Vercel Hobby runs Python/FastAPI functions without a card (2 GB, up to
  300 s, streaming), but functions keep no state between invocations.

## Decision

1. **The server keeps no session state.** A *revision* is an immutable value the client holds:
   `{scenario_id, scenario_version, shocks, committed_patch, plan}`. Its id is
   `sha256(canonical JSON)[:16]`. Every endpoint receives the revision it acts on.
2. **Never trust the client's plan.** Impact, evaluate and apply recompile the problem and run the
   independent validator. Apply accepts a plan only if it validates with zero hard violations.
3. **Staleness:** recovery options carry `base_revision_id`. Apply recomputes the hash of the
   submitted current revision; mismatch → `409 STALE_REVISION`.
4. **Undo/reset are client-side history** of server-verified revisions (deterministic, testable),
   so no anonymous writes can ever touch a shared scenario. Session isolation is structural.
5. **Agent run = one streaming POST** (`text/event-stream` over fetch) that ends when the bounded
   loop ends (budget ≤ 90 s), so nothing must outlive the request.
6. **Single origin:** FastAPI serves the Next.js static export, so no CORS in production.
7. **Fallbacks:** Render free Docker container (same image), then a recorded-run *replay* mode that
   is labelled as a replay. Neither may be presented as a live model call.

## Consequences
- Spec endpoints become: `GET /api/demo` (scenario + presets + initial revision),
  `POST /api/impact`, `POST /api/evaluate`, `POST /api/recover` (SSE), `POST /api/search`
  (deterministic fallback), `POST /api/apply`, `POST /api/report`, `GET /api/health`.
- Global inference budget cannot live in process memory across instances. Mitigations: hard
  per-run caps, per-instance rate limit, Nebius-side spend limit if available (to verify), and a
  small cache keyed by `(revision_id, priorities, model, prompt_version)` labelled "cached".
- OR-Tools cold start on Vercel is a known unknown → smoke deploy as soon as the owner connects an account.
