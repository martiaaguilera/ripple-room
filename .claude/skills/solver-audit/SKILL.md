---
name: solver-audit
description: Verify Ripple Room's scheduling truth engine and agent invariants with deterministic tests only (no live model calls). Use before and after changing domain, solver, agent tools, prompts or evaluation code.
allowed-tools: Bash(uv run pytest*) Bash(uv run ruff*) Bash(uv run mypy*) Bash(uv run python*)
---

# Solver and agent audit

Run from `services/api`:
1. `uv run ruff check . && uv run ruff format --check . && uv run mypy app`
2. `uv run pytest -q` — must be all green. Key suites: `test_regression_fixtures.py` (baseline feasible,
   truck +35 breaches with verified recoveries, +90 provably infeasible), `test_engine.py` (validator,
   fuzz: no verified plan ever fails validation), `test_agent_signals.py` (c19 / c09 reproductions).
3. Harness check without cost: `uv run python ../../scripts/evaluate.py --agent mock` then delete the
   generated `docs/evaluation/*mock*` files — mock numbers are never published as results.
4. Invariants that must hold (see CLAUDE.md): solver plans are re-validated; `unknown` is never green;
   the model only proposes allow-listed patches; preferences never relax hard constraints; options are
   attributed to the model only when `origin == "model"`.
5. NEVER run `--agent live`, `smoke_nebius.py` or `check_judge_demo.py` (they spend real credits)
   unless the owner explicitly approved it in this conversation.
