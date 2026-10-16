# ADR-001 — Product scope for the hackathon build

- **Status:** Accepted · 2026-10-16
- **Context sources:** owner brief (local, not committed), `docs/research/rules-snapshot.md`,
  `docs/research/competition.md`, `docs/research/api-capabilities.md`

## Decision

Ship **one** polished, fully working scenario — *Signal Night* at the fictional *Bay Hall*
(`signal-night-v1`) — with four disruption presets, a deterministic truth engine, a bounded
Nemotron agent, and Before/After compare + Apply/Undo. Track: **Best Apps and Agents**.

### In scope (P0)
- Seeded fictional event: 15 tasks (incl. 3 milestones), 7 active + 2 standby resources, DAG with
  one `waived_if_deferred` edge, hard 18:00 doors deadline.
- Presets (all outcomes proven by tests in `services/api/tests/test_regression_fixtures.py`):
  | Preset | Do-nothing outcome | Verified recoveries (minimal, from exhaustive search) |
  |---|---|---|
  | Truck +35 | doors ready 18:15 (breach) | rent trolley (€35) · line check (€0, quality trade-off) |
  | AV tech out 15:30–16:30 | 18:30 (breach) | rental trolley · backup AV (€127.50) · line check · short briefing |
  | Dock +20 | 17:55 (absorbed by slack) | none needed |
  | Truck breakdown +90 | 19:10 | **none** — provable bound 18:30 |
- Intervention vocabulary (typed): `activate_resource`, `compress_task`, `defer_task`,
  `assign_resource`, `pin_start`.
- Nemotron agent on Nebius Token Factory with trusted tools; solver-verified options; labelled
  deterministic fallback.

### Where the AI must earn its place (honest framing)
Exhaustive search over this small menu takes ~40 ms, so the model is **not** needed to find a
feasible patch here. The model is used where a solver cannot help:
1. Turning a free-text incident report ("driver says 40 more minutes, M-30 is jammed") into a typed shock.
2. Interpreting coordinator priorities ("no extra spend", "sponsors need vendor tables") into patch choices.
3. Composing patches outside the menu (resequencing via `pin_start` / `assign_resource`) and revising after verifier feedback.
4. Explaining trade-offs and drafting a crew change notice (who must be told what, by when).
The evaluation harness compares agent proposals to the exhaustive-search Pareto set and reports
the result as measured, whatever it is.

### Out of scope
Multi-day plans, real maps/GPS, auth/multi-tenant, external calendar integrations, 3D scenes,
billing, safety-critical claims. Tavily only if it becomes genuinely useful (currently not planned).

## Consequences
- Fixture changes must keep the regression tests green; tune data, never the outcome logic.
- Differentiation per competition research: same-screen graph + Gantt cascade with minutes,
  verifier verdict per patch including a visible rejection, human-controlled apply/undo, and a
  crew change notice. We do not claim to be the first LLM + CP-SAT scheduler.
- Name collision noted ("Ripple", Sep 2026 hackathon project); keep "Ripple Room" unless owner decides otherwise.
