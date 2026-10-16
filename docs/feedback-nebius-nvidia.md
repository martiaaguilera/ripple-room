# Nebius Token Factory + NVIDIA Nemotron: working notes for the feedback form

Empirical observations are dated and link to evidence. Opinions are marked as such.

## Observations (empirical)
- 2026-10-16: `GET /v1/models?verbose=true` returns `pricing`, `context_length`, `supported_features`
  (`tools`, `reasoning`) and `regions` per model — enough to choose a model programmatically.
  Evidence: `docs/evidence/nebius-smoke-20261016T211619Z.json`.
- 2026-10-16: Nemotron 3 Ultra is listed only in `us-central1`; Super, Nano and Lightning in `eu-north1`.
- 2026-10-16: Super answered a trivial prompt in 649 ms and a tool-calling prompt in 933 ms; the assistant
  message carried a reasoning field even for "Reply with exactly: READY" (content came back as "\n\nREADY").
- 2026-10-16: With a deliberately loose tool schema (`items: {type: object}`), Super invented field names
  (`action`, `resource`). With an explicit enum-typed schema in the real agent it produced valid arguments
  on every call in 3 runs (20 calls). Lesson: give the model precise JSON Schemas.
- 2026-10-16: In 3 multi-step runs Super followed the tool protocol end to end (get_situation →
  list_interventions → evaluate_patch… → submit_options), revised after verifier rejections, and in the
  impossible case submitted zero options instead of inventing one.
- 2026-10-16: Priority alignment was imperfect: told "protect the guest experience; spending is fine",
  it still ranked a guest-impacting option first.

## Onboarding friction (empirical)
- Docs disagree on whether `response_format: json_schema` is supported (see `docs/research/api-capabilities.md`).
- Two hostnames appear in docs (`api.studio.nebius.com` legacy vs `api.tokenfactory.nebius.com`).

## To record later
- Minutes from signup to first successful call (owner to supply).
- Rate-limit headers seen under load; credit consumption over the judging period.
