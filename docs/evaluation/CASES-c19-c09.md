# Two cases that explain what the agent adds — and what it still misses

All facts below are reproducible without a model: `uv run pytest tests/test_agent_signals.py`.
Agent behaviour is quoted from the two live runs (v2, v4), **one run per version per case** — no
statistical claim is made from them.

## c19 — setup team away 14:30–15:30 (balanced priorities): a strategy outside the playbook
- **Playbook search** (every combination of up to four standard fixes: rental trolley, backup AV
  technician, full soundcheck/briefing cuts, deferring vendor work): **no verified recovery**.
- **Greedy baseline:** no verified recovery.
- **What works:** a *combination* the playbook cannot express — a second person on stage rigging
  (`add_helper`) plus a line check (`compress_task soundcheck → 15`). Verified, €0, ready by 18:00.
- **Agent, v2:** found and verified *transport crew helps rigging + line check* — a recovery in a case
  where both deterministic baselines report none (worse than the oracle's choice under the ranking,
  because it pulls the transport crew off unloading).
- **Agent, v4:** found and verified *event lead helps rigging + line check* — exactly the oracle's best.
- **The novel contribution:** using a person who is not assigned to the stalled work as a helper, and
  pairing it with a partial service cut, discovered through tool use (`get_situation`,
  `evaluate_patch`) and confirmed by the verifier. The extended exhaustive oracle also finds it,
  because it enumerates the same action space; the agent needed 6 verifier checks (v2) and 2 (v4)
  versus the oracle's 123 combinations for this case.

## c09 — truck +65 min (balanced): combined changes remain a weakness
- No single change and no pair of changes from the full action space recovers it (test asserts this).
- The oracle's recovery needs **three simultaneous changes**: rental trolley + event lead helps
  rigging + soundcheck cut to 20 min (€35, ready by 18:00).
- **Agent, v2 and v4:** no verified recovery (budget exhausted in v2; submitted without one in v4).
  Playbook search and greedy also fail.
- Changes made since (not yet measured live): rejected proposals now report
  `minutes_gained_vs_doing_nothing`, and the prompt asks the agent to combine fixes that each gain
  minutes; idle people on the critical chain are listed explicitly.

## How to re-measure (requires owner approval for live inference)
`uv run python scripts/evaluate.py --agent live --cases c19,c09` — about 2 × $0.012.
