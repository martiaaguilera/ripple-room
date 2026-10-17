# Feedback: Nebius Token Factory and NVIDIA Nemotron

For the Devpost feedback field. Facts are dated and point to evidence in this repo. Opinions are marked
**(opinion)**. We used Token Factory only; we did not use Nebius AI Cloud.

## What we used, and for what
- **Model:** `nvidia/nemotron-3-super-120b-a12b` (Nemotron 3 Super) on Nebius Token Factory, global
  endpoint `https://api.tokenfactory.nebius.com/v1/`, OpenAI-compatible chat completions with native
  tool calling.
- **Use 1, recovery agent:** a bounded tool loop (up to 8 model calls and 6 verifier checks per run).
  The model reads the situation and proposes typed fixes; an OR-Tools CP-SAT verifier accepts or
  rejects each one.
- **Use 2, intake:** one forced tool call that turns a free-text incident description into typed
  incidents and priorities.
- **Not tested:** Nemotron 3 Ultra, Lightning, Nano, structured output via `response_format`, and Nebius
  AI Cloud.

## Onboarding (zero to first call)
- Once we had a key, the first verbose model listing and the first tool call both worked on the first
  attempt with a plain HTTP client (16 Oct 2026). Evidence: `docs/evidence/nebius-smoke-20261016T211619Z.json`,
  `docs/evidence/nebius-smoke-20261016T211627Z.json`.
- `GET /v1/models?verbose=true` was the most useful single call: it returned 28 models, and for each
  one its price, context length, `supported_features` and `regions`. We used it to choose the model and
  to compute cost per run.
- A bank card is required at sign-up ([billing docs](https://docs.tokenfactory.nebius.com/other-capabilities/billing-new.md)).
  **(opinion)** For a global hackathon this is the biggest hurdle; the hackathon FAQ also notes that
  billing does not support every country.

## Documentation inconsistencies (checked 16 Oct 2026)
1. **Structured output.** The chat-completions OpenAPI field description says only `json_object` or `text`
   is supported ([API reference](https://docs.tokenfactory.nebius.com/api-reference/inference/create-chat-completion.md)).
   The structured-output guide documents `json_schema` with `"strict": true`
   ([JSON guide](https://docs.tokenfactory.nebius.com/ai-models-inference/json.md)). The text-generation
   example uses vLLM-style `guided_json` instead
   ([example](https://docs.tokenfactory.nebius.com/api-reference/examples/text-generation.md)).
   We avoided the question by using tool calls with strict schemas.
2. **Hostnames.** The docs use `api.tokenfactory.nebius.com`. The Nemotron cookbook recommends the
   regional `api.tokenfactory.us-central1.nebius.com`
   ([cookbook](https://github.com/nebius/token-factory-cookbook/tree/main/models/nemotron)), while the
   public-serverless page warns that regional URLs "can stop working"
   ([public serverless](https://docs.tokenfactory.nebius.com/public-serverless.md)). The legacy
   `api.studio.nebius.com` still answers with a 401. We used the global host.
3. **Model IDs.** Casing differs between models (`nvidia/Nemotron-3-Ultra-550b-a55b`,
   `nvidia/nemotron-3-super-120b-a12b`, `nvidia/Nemotron-3_5-Lightning`). For Nano, the cookbook card
   uses `nvidia/nvidia-nemotron-3-nano-30b-a3b`; the live list returns `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`.
4. **Price.** We could not find the Super price on a public Nebius page we could read (the price page
   is a JavaScript app). The live list confirmed $0.30 / $0.90 per million tokens.
5. **Regions.** The live list shows Super and Ultra only in `us-central1`, Nano and Lightning in
   `eu-north1`. Our calls to Super through the global host worked anyway. **(opinion)** A sentence in the
   docs on how the global host routes to a model's region would remove the guesswork.
6. **Reasoning fields.** The response schema has both `reasoning_content` and `reasoning`. We read
   either one.

## Model behaviour (Nemotron 3 Super, measured)
Benchmark data: 20 fixed cases, two prompt versions, **one run per version**. Files:
`docs/evaluation/COMPARISON-v2-v4.md` and the two `RESULTS-live-*.md` files.
- **Tool protocol: good.** 40 benchmark runs made 283 model calls; no run ended with an error. In our
  three recorded agent runs the model followed get_situation → list_interventions → evaluate_patch →
  submit_options, and revised after verifier rejections.
- **Honest when stuck.** With a 90-minute truck breakdown it submitted zero options and named 18:30 as
  the earliest possible time (`docs/evidence/live-run-truck-breakdown-90-20261016T211755Z.json`).
- **Schemas matter.** With a loose tool schema (`items: {type: object}`) it invented field names
  (`action`, `resource`) (`docs/evidence/nebius-smoke-20261016T211627Z.json`). With explicit
  enum-typed schemas, all 19 tool calls in the three recorded agent runs were valid.
- **Forced tool choice works.** Forcing `submit_options` by name on the last allowed call cut runs that
  ran out of budget from 7/20 to 0/20.
- **Reasoning is on by default.** Even "Reply with exactly: READY" came back with a reasoning
  field and content `"\n\nREADY"`. Single calls took from about 0.5 s to 11.3 s; the slowest ones had
  the most completion tokens. Median time per recovery was 18.4–19.5 s.
- **Stops exploring early.** In the v4 run it made 3.5 verifier checks per case on average. Under
  "protect the guests" priorities it often missed a free fix that the exhaustive search found.
- **Priority alignment is imperfect.** Told "Protect the guest experience; spending is fine", it still
  put a guest-impacting option first (`docs/evidence/live-run-truck-delay-35-20261016T211726Z.json`).
  Its own top pick did match our deterministic ranking in 15 of 16 v4 cases.
- **Overall (honest reading):** the agent was not better overall than our deterministic playbook search
  (best option equal to the oracle's: 9/17 and 7/17 vs 8/17). It did find one recovery the playbook
  cannot express (case c19).
- **Cost:** $0.2435 and $0.2207 for 20 runs at list price, about one cent per recovery.

## Billing and spend control
- **Owner report (not independently verified):** the trial period ends before the judging window
  (1–15 Dec 2026), and the dashboard warns that usage may continue on the linked card once the balance
  reaches $0.
- **Why it matters for this hackathon:** the rules require the demo to stay free for judges until
  15 Dec. A public demo that calls the model can, in the worst case, keep spending after the credits
  run out.
- **What we did:** app-side limits (kill switch, daily token and run budgets, per-IP limits). These are
  not a provider-level cap, and we could not confirm from the docs we read whether a hard "stop at $0"
  setting exists.
- **(opinion)** We were careful with spend because of this warning; a clearer guarantee would have
  let us test more.

## What we would improve (opinion)
1. A hard spending cap or "stop at $0" switch per project, shown next to the card warning.
2. Show the expiry date of each promo credit on the balance page.
3. A hackathon credit option that lasts through the judging period.
4. One answer on structured output: what `response_format` supports, per model, in both the API
   reference and the guide. Add it to `supported_features`.
5. One canonical model ID per model in every doc, matching `/v1/models`.
6. A short Nemotron-specific page: how to turn reasoning off, what `reasoning_effort` does, and which
   reasoning field is returned.
7. A readable price page, or a link to the verbose model list as the source of truth.

## Would we build with it again?
**(opinion)** Yes. The OpenAI-compatible API, native tool calling and the verbose model list made the
integration quick, and Nemotron 3 Super was reliable with tools at about one cent per recovery. We
would want a provider-level spending cap before leaving a public demo running for weeks.
