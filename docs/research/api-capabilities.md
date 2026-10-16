# Nebius Token Factory API capabilities for NVIDIA Nemotron

All sources accessed **2026-10-16**. No authenticated API call was made because we had no key. Every model ID below comes from public docs or marketing pages and **must be confirmed with a live `GET /v1/models`** (see the last section).

Source keys:

- [Q] Quickstart: https://docs.tokenfactory.nebius.com/quickstart (https://docs.nebius.com/studio now redirects here)
- [SW] Switch to Token Factory: https://docs.tokenfactory.nebius.com/switch.md
- [API] API intro/auth: https://docs.tokenfactory.nebius.com/api-reference/introduction.md
- [OAS] Chat completions OpenAPI (spec version `20261012-dfdbe18ea`): https://docs.tokenfactory.nebius.com/api-reference/inference/create-chat-completion.md
- [LM] List models: https://docs.tokenfactory.nebius.com/api-reference/examples/list-of-models.md and https://docs.tokenfactory.nebius.com/api-reference/models/list-models.md
- [FC] Function calling: https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling.md
- [JS] Structured output: https://docs.tokenfactory.nebius.com/ai-models-inference/json.md
- [TG] Text generation example (guided_json): https://docs.tokenfactory.nebius.com/api-reference/examples/text-generation.md
- [RL] Rate limits: https://docs.tokenfactory.nebius.com/ai-models-inference/rate-limits.md
- [OV] Inference overview: https://docs.tokenfactory.nebius.com/ai-models-inference/overview.md
- [PS] Public serverless: https://docs.tokenfactory.nebius.com/public-serverless.md
- [CDP] Dedicated control/data plane (region table), from https://docs.tokenfactory.nebius.com/llms-full.txt (page "Control & Data Plane")
- [BIL] Billing: https://docs.tokenfactory.nebius.com/other-capabilities/billing-new.md
- [DEP8] August 2026 deprecations: https://docs.tokenfactory.nebius.com/august-2026-deprecation-notice.md
- [NP] Nebius Nemotron inference page: https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference
- [NH] Nebius Nemotron healthcare page: https://nebius.com/services/token-factory/nemotron
- [CB] Cookbook: https://github.com/nebius/token-factory-cookbook/tree/main/models/nemotron (files README.md, nemotron3-super-120B.md, nemotron3-ultra-550b-a55b.md, nemotron3-nano-30b.md, run_nemotron.ipynb, read raw from raw.githubusercontent.com)
- [HF-S] https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16 ; [HF-U] https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16 ; [HF-N] https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 ; [HF-L] https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16
- [VL] vLLM Lightning launch blog: https://vllm.ai/blog/2026-08-10-nemotron-3-5-lightning-vllm

---

## 1. Base URLs, auth, regions

| Host | Status | Evidence |
|---|---|---|
| `https://api.tokenfactory.nebius.com/v1/` | **Current canonical.** Used in every docs page. It is the `eu-north1` data-plane URL. | [Q][SW][API][OAS servers][CDP] |
| `https://api.tokenfactory.us-central1.nebius.com/v1/` | Regional. The cookbook and marketing pages use it for Super, Ultra and Nano. | [CB][NH] |
| `https://api.tokenfactory.eu-west1.nebius.com` | Regional data plane (dedicated endpoints) | [CDP] |
| `https://api.studio.nebius.com/v1/` | **Legacy** (AI Studio). It still answers: unauthenticated `GET /v1/models` returns `401 {"detail":"Couldn't authenticate. Reason: token is not present"}` (my curl, 2026-10-16). It is not in the current docs. | live probe |

- I probed all three hosts without a token. Each returned the same 401 JSON, so they are all live gateways.
- **Auth:** `Authorization: Bearer $NEBIUS_API_KEY` [API]. Keys are created at https://tokenfactory.nebius.com/project/api-keys and "You cannot open it later" [API].
- Optional query param `ai_project_id` selects a project [OAS][LM].
- **Region caveat (important):** public serverless endpoints are "Global". "If your integration relies on a specific `base_url` that includes a region (e.g. `api.tokenfactory.us-central1.nebius.com`), that URL can stop working if the endpoint's processing region changes." [PS] This means **the global host is the safe default**, even though the cookbook cards recommend us-central1 for Ultra ("Recommended endpoint | `https://api.tokenfactory.us-central1.nebius.com/v1/`" [CB]).
- The cookbook notebook calls **all three** Nemotron models (Lightning, Super, Ultra) through the global `https://api.tokenfactory.nebius.com/v1/` [CB run_nemotron.ipynb]. NOT VERIFIED live.
- Other endpoints exist: `/v1/completions`, `/v1/embeddings`, `/v1/responses` ("Create a response"), and files and datasets (from the docs index https://docs.tokenfactory.nebius.com/llms.txt).

## 2. Nemotron model IDs (as published)

| Model | Model ID string | Context | Price in/out per 1M | Confidence | Source |
|---|---|---|---|---|---|
| Nemotron 3 Ultra 550B-A55B | `nvidia/Nemotron-3-Ultra-550b-a55b` | 1M ("1,024K") | **$1.00 / $3.00** | **High** (same ID in 4 places) | [NP][CB] |
| Nemotron 3 Super 120B-A12B | `nvidia/nemotron-3-super-120b-a12b` (all lowercase) | 256K [CB] (HF says up to 1M) | $0.30 / $0.90 (**third-party only**, NOT VERIFIED on a Nebius page) | **High** for the ID | [NH][CB][DEP8] |
| Nemotron 3.5 Lightning 30B-A3B | `nvidia/Nemotron-3_5-Lightning` (note the underscore) | 1M ("1,024K") | **$0.06 / $0.24** | **High** | [NP][CB][DEP8] |
| Nemotron 3.5 Super VL 120B-A12B | `nvidia/Nemotron-3.5-Super-VL` | NOT VERIFIED | **$0.30 / $0.90** | Medium (one marketing snippet and one link) | [NP] |
| Nemotron 3 Nano 30B-A3B | **Conflicting:** `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` [NP catalog link; CB README comment] vs `nvidia/nvidia-nemotron-3-nano-30b-a3b` [CB card] | 262K | $0.06 / $0.24 [NP] | **Low.** The cookbook lists it under "Models not currently featured" | [NP][CB] |

Third-party source for the Super price: https://cloudprice.net/models/nebius/nvidia/nemotron-3-super-120b-a12b and https://www.getmaxim.ai/bifrost/model-library/compare/nebius/nemotron-3-super-120b-a12b.md (via search snippet, not opened).

**Deprecated or removed (do not use):**

- `nvidia/Llama-3_1-Nemotron-Ultra-253B-v1` was removed from serverless on **31 Aug 2026**. The suggested replacement is `nvidia/nemotron-3-super-120b-a12b` [DEP8].
- `nvidia/Nemotron-3-Nano-Omni` was removed **31 Aug 2026**. The suggested replacement is `nvidia/Nemotron-3_5-Lightning` [DEP8].
- `Llama-3.3-Nemotron-Super-49B` did not appear in any current Nebius doc, cookbook or deprecation page I read. **NOT VERIFIED / assume unavailable.**
- "Token Factory does not automatically reroute requests from deprecated models." [DEP8]

Other details:

- **Model ID casing is inconsistent** (`Nemotron-3-Ultra-550b-a55b` vs `nemotron-3-super-120b-a12b` vs `Nemotron-3_5-Lightning`). Copy the IDs exactly from `/v1/models`.
- Serving details from [NP]: Ultra is FP4, Lightning BF16, Nano FP8. All have a "Public endpoint available".
- **Fast flavor:** "append `-fast` to the model name" for lower latency and a higher price [OV]. NOT VERIFIED whether any Nemotron model has a `-fast` variant.

## 3. Capabilities

### Tool / function calling

- The platform supports OpenAI-format `tools`. `tool_choice` accepts `none` | `auto` | `required` | a named function [OAS][FC]. "The model **does not execute** the functions itself" [FC].
- Per model:
  - Ultra: "Tool calling | Available", "Reasoning | Available" [CB].
  - Super: "Supports function calling and structured output out of the box" [CB].
  - Nano: "Supports function calling and structured output" [CB].
  - Lightning: [NP] says "agentic reasoning, coding, and tool use", and vLLM serves it with `--tool-call-parser qwen3_coder` [VL].
- No `parallel_tool_calls` field is in the Nebius request schema. The schema has `additionalProperties: true` [OAS]. NOT VERIFIED.

### Structured output

- `response_format` enum: `text` | `json_object` | `json_schema` (with a `json_schema` object) [OAS ResponseFormat][JS].
- **Doc inconsistency:** the same OpenAPI field description says "Only {'type': 'json_object'} or {'type': 'text' } is supported." [OAS]. The JSON guide documents `json_schema`, including a `"strict": true` example [JS].
- `guided_json` passed via `extra_body` (vLLM-style) appears in the official text-generation example [TG].
- "Some models are better in providing JSON ... Use `JSON mode` tag in on a model card" [JS]. Whether the Nemotron models carry that tag is NOT VERIFIED. Check `supported_features` in verbose `/v1/models`.
- Tip from [JS]: put the schema in the prompt **and** in `response_format`.

### Reasoning on/off and output fields

- The Nebius request schema has **`reasoning_effort`**: `none|minimal|low|medium|high|xhigh|max` [OAS]. NOT VERIFIED how Nemotron maps these values.
- The Nebius response message and stream delta schemas have **both `reasoning_content` and `reasoning`** fields ("The reasoning content of the message.") [OAS]. Usage reports `reasoning_tokens` [OAS]. Code should read either field.
- From the NVIDIA model cards (self-hosted vLLM or SGLang, **not Nebius-specific**):
  - The documented on/off switch is `extra_body={"chat_template_kwargs": {"enable_thinking": True|False}}`. Reasoning is ON by default [HF-S][HF-U][HF-N][HF-L].
  - Super also supports `{"enable_thinking": True, "low_effort": True}` and a `reasoning_budget` [HF-S].
  - Coding agents should add `"force_nonempty_content": True` [HF-S][HF-L].
  - Ultra: "when calling the chat completions endpoint with `tools`, you **must** set `"chat_template_kwargs": {"enable_thinking": true, "force_nonempty_content": true}`" [HF-U].
  - Recommended sampling is "`temperature=1.0` and `top_p=0.95` across all tasks" [HF-S].
  - vLLM's Lightning example reads `choice.message.reasoning` [VL].
- Nebius says its API "Supports the full set of vLLM parameters" [OV], and the request schema allows extra properties [OAS]. That suggests `chat_template_kwargs` is passed through. **NOT VERIFIED on Nebius.** Test it live.
- No evidence was found of a "/think" system-prompt toggle for Nemotron 3. That toggle belonged to older Llama-Nemotron models. NOT VERIFIED for Nemotron 3 on Nebius.

### Context / limits

- `max_tokens` "If omitted or set to null, **defaults to 8192 tokens**" [OAS]. `max_completion_tokens` "including visible output tokens and reasoning tokens" [OAS].
- Context: Ultra and Lightning 1M, Nano 262K [NP]. Super 256K on Token Factory [CB], although the model supports up to 1M [HF-S].
- A third-party listing reports a 32,768 max output for Super on Nebius. NOT VERIFIED.

## 4. Pricing, rate limits, credits

- Prices are in the table above. Verbose `/v1/models` returns `pricing.prompt` and `pricing.completion` per token [LM]. **That is the authoritative check.** The official pricing page https://tokenfactory.nebius.com/organization/prices is a JS app that I could not read.
- Rate limits are **dynamic** and evaluated in 15-minute windows:
  - Above 80% usage the limit grows ×1.2. Below 50% it shrinks ÷1.5. The cap is 20× base [RL].
  - The doc's "Visual example" baseline is **60 RPM / 400,000 TPM**. That is illustrative. The real defaults are shown at https://tokenfactory.nebius.com/project/rate-limits [RL].
  - Going over returns HTTP 429 with `Retry-After` and `x-ratelimit-*` headers. Requests may still be served with `x-ratelimit-over-limit: yes` [RL].
  - Verbose `/v1/models` also exposes `per_request_limits` (tokens_per_minute, requests_per_minute) [LM].
- `service_tier`: `auto` (default) | `default` | `over-limit` | `flex` | `no-limit` [OAS]. A `529 "System is overloaded"` error is documented [OAS].
- **Credits:**
  - "Upon first sign-up, you receive **$1 in trial credit**, valid for **30 days**." Billing setup with a **bank card is mandatory** [BIL].
  - Hackathon promo: $25 with code `NEBIUS-DEVPOST-GLOBAL26`, plus $25 from the Builders Program (see `rules-snapshot.md`). Apply it via Top up → "With promo code" [BIL].
  - Promo codes "usually have an expiration date" [BIL]. The expiry for the hackathon code is NOT VERIFIED. It matters because the demo must stay live to 15 Dec 2026.

## 5. List models

```bash
curl https://api.tokenfactory.nebius.com/v1/models -H "Authorization: Bearer $NEBIUS_API_KEY"
curl -s 'https://api.tokenfactory.nebius.com/v1/models?verbose=true' -H "Authorization: Bearer $NEBIUS_API_KEY"
```

The verbose RichModel fields are `id, name, context_length, architecture, quantization, pricing, per_request_limits, status, status_reason, regions, supported_features, supported_sampling_parameters` [LM].

## 6. Known quirks

1. There are three live hostnames (global, us-central1, legacy studio). The docs say regional URLs for public endpoints "can stop working" [PS].
2. Model-ID casing and separators are inconsistent across Nemotron models, and the Nano ID conflicts between sources (§2).
3. `response_format` docs contradict each other (json_schema documented vs "Only json_object or text") [OAS][JS]. Plan a fallback: `json_object` plus a schema in the prompt plus client-side validation.
4. The default `max_tokens=8192` can be used up entirely by reasoning tokens. Set `max_tokens` explicitly, or turn reasoning off for fast calls.
5. The reasoning text may come back in `reasoning_content` **or** `reasoning` [OAS]. Handle both, and handle an empty `content`. That case is why the HF cards suggest `force_nonempty_content` [HF-S][HF-U].
6. Models are deprecated on a schedule (June and Aug 2026 notices) with no auto-reroute [DEP8]. Keep IDs in env vars.
7. Public endpoints may log data for speculative decoding unless Zero Data Retention is enabled. Storage is in Finland (llms-full.txt, Data Location §5.1). NOT VERIFIED in detail.

## 7. Recommended configuration

```env
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_MODEL_PLANNER=nvidia/Nemotron-3-Ultra-550b-a55b
NEBIUS_MODEL_PLANNER_FALLBACK=nvidia/nemotron-3-super-120b-a12b
NEBIUS_MODEL_FAST=nvidia/Nemotron-3_5-Lightning
NEBIUS_MODEL_FAST_ALT=nvidia/nemotron-3-super-120b-a12b
# NEBIUS_BASE_URL_ALT=https://api.tokenfactory.us-central1.nebius.com/v1/   (only if Ultra 404s on global)
```

| Var | Value | Confidence | Why |
|---|---|---|---|
| NEBIUS_BASE_URL | global `api.tokenfactory.nebius.com/v1/` | **High** | Canonical in every doc. The [PS] warning argues against pinning a region. |
| NEBIUS_MODEL_PLANNER | `nvidia/Nemotron-3-Ultra-550b-a55b` | **High** that the ID exists, **Medium** that it works on the global host | The track text says "Reach for Nemotron 3 Ultra when you need serious reasoning". $1/$3. |
| NEBIUS_MODEL_FAST | `nvidia/Nemotron-3_5-Lightning` | **High** | Cheapest ($0.06/$0.24), 1M context, tool use, featured as the default by the cookbook. |
| Fallback | `nvidia/nemotron-3-super-120b-a12b` | **High** (ID), **Low** (price) | Named "Super" in the track text. Mid-tier. |
| Nano | avoid unless confirmed | Low | Conflicting IDs, "not currently featured". Lightning replaces it. |

The Best Apps track text names "Nano or Super" for fast calls. Lightning is NVIDIA's newer 30B-A3B model. If the judges read "Nano" literally, Super is the safe named alternative.

### Must confirm with a live authenticated `GET /v1/models?verbose=true`

1. The exact `id` strings (casing) for Ultra, Super, Lightning, Super VL and Nano, and that each has `status` available on the **global** host.
2. Whether Ultra and Super are reachable on the global host or only on us-central1 (check `regions`).
3. `context_length`, `pricing.prompt` and `pricing.completion` for each one. This matters most for the Super price, which is third-party only.
4. `supported_features`: tools / function calling, JSON mode, json_schema, reasoning.
5. `per_request_limits` (RPM and TPM) for our account. Also check the rate-limits page.
6. Whether any `-fast` Nemotron variants exist.

Also confirm with test calls (not just the list):

7. That `extra_body.chat_template_kwargs.enable_thinking=false` turns reasoning off, and whether `reasoning_effort` works.
8. Which field carries the reasoning text (`reasoning_content` vs `reasoning`).
9. Whether `response_format: json_schema` with `strict` is enforced, and whether `guided_json` works.
10. `tools` combined with reasoning on Ultra: does it need `force_nonempty_content`, and what does `tool_choice: "required"` do?
11. The promo credit balance and expiry once `NEBIUS-DEVPOST-GLOBAL26` is applied.
