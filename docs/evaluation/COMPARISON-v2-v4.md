# Live evaluation: prompt v2 vs v4 (measured)

Both runs: 20 fixed cases, `nvidia/nemotron-3-super-120b-a12b` on Nebius Token Factory, same scenario,
same budgets (8 model calls, 6 verifier checks, 80k tokens, 90 s), same deterministic ranking.
Raw data: `results-live-20261016T223713Z.json` (v2) and `results-live-20261016T224613Z.json` (v4).
**One run per version** — differences of one or two cases are within run-to-run noise.

v4 = v2 + (a) the last allowed model call forces `submit_options`; (b) a server-verified
"keep the current plan" candidate `c0` exists when slack absorbs the incident.

| Metric | v2 | v4 | Playbook search | Greedy |
|---|---|---|---|---|
| Verified recovery found when one exists | 16/17 | 16/17 | 15/17 | 15/17 |
| Honest "none" when none exists | 3/3 | 3/3 | 3/3 | 3/3 |
| Options failing independent re-validation | 0 | 0 | 0 | 0 |
| Best option = oracle (preference ranking) | 9/17 | 7/17 | 8/17 | 6/17 |
| Best option with more preference breaches than oracle | 0 | 0 | 0 | 0 |
| Runs that ended by exhausting the budget | 7/20 | **0/20** | – | – |
| Model's own #1 = deterministic #1 | 10/10 | 15/16 | – | – |
| Median / p95 latency | 19.5 s / 49.3 s | 18.4 s / 33.4 s | 0.08 s | 0.11 s |
| Tokens (total, 20 runs) | 652,167 | 597,797 | – | – |
| Cost at list price (prompt $0.30/M, completion $0.90/M) | $0.2435 | $0.2207 | 0 | 0 |
| Proposals the verifier did not accept | 41 | 29 | – | – |
| Beyond-playbook actions tried | 69 | 49 | – | – |

## Does v4 outperform v2?
- **Yes, on reliability:** every v4 run ended with the model's own choice (0 budget exhaustions vs 7),
  p95 latency fell from 49 s to 33 s and cost fell 9 %.
- **No, on option quality:** best-option-matches-oracle went from 9/17 to 7/17. With one run each this is
  not a statistically meaningful change in either direction; the honest reading is "no improvement".
- The `c0` fix did not work as intended: in c14 (absorbed dock delay) the model still submitted a change
  (event lead helping rig) instead of `c0`, so the best option was not "change nothing".

## Where the agent beats the baselines
- c19 (setup team out 14:30–15:30): agent finds a verified, zero-cost recovery in both runs; playbook
  search and greedy find none (the fix needs a helper, outside the playbook).
- c03, c04 (v2 and v4), c07/c08 (v2): agent's best equals or beats playbook search.

## Three most important remaining weaknesses (by measured impact)
1. **Narrow exploration under "protect guests" priorities** (c01, c05, c06, c20; regret 9–275 points):
   the agent stops after its first verified options (mean 3.5 verifier checks in v4) and misses the
   zero-cost, no-guest-impact fix (event lead helps rigging) or the paid no-compromise fix.
2. **Ignores the free option when doing nothing is enough** (c14): it proposes changes even though the
   verified `c0` exists.
3. **Misses combination fixes** (c09: needs a helper plus a trolley; only the exhaustive oracle finds it).

## Prioritised fixes (measurable, no new features)
1. Always include the server-verified `c0` in the final option set (deterministic; expected to fix c14).
2. Show the agent, in `get_situation`, which people are idle during the driving path (a fact the server
   already computes), so helper fixes are visible without a search — re-measure on the guest cases.
3. Raise the verifier-check budget from 6 to 8 only if (2) is not enough — measure cost per run first.

Live re-measurement is **paused** until the owner authorises more inference spend.

## Run integrity (from the raw JSON)
- Model calls: 146 (v2) + 137 (v4) = 283; runs that ended with a provider error: 0 in both.
