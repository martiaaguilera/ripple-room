# Ripple Room: deploying the monorepo to Vercel Hobby

Research date: 16 Oct 2026. All URLs are official Vercel docs and were fetched on 2026-10-16. "NOT VERIFIED" means the claim does not appear in the official docs I read. It is an inference or common practice.

## TL;DR

Use **Vercel Services (Beta, available on all plans)**. It gives one project and one domain. The vercel.json at the repo root declares two services: a FastAPI service rooted at `services/api/` and a Next.js service rooted at `apps/web/`. Top-level rewrites send `/api/*` to FastAPI and everything else to the web service. FastAPI receives the **original path** (`/api/...`), which matches our routes. You don't need a shim or `api/index.py`, and you don't need to copy `out/` into `public/`.

## 1. Hobby plan terms and limits

- **Non-commercial only.** "Hobby teams are restricted to non-commercial personal use only." Commercial means "any Deployment that is used for the purpose of financial gain of anyone involved in any part of the production". Examples: payments, ads, selling a product, being paid to build or host the site. A free, ad-free hackathon demo fits "personal, non-commercial". Whether a hackathon **cash prize** counts as "financial gain" is not addressed: NOT VERIFIED (ambiguous). To be sure, ask Vercel Support. https://vercel.com/docs/limits/fair-use-guidelines#commercial-usage
- **Monthly included usage (Hobby):**
  - 1,000,000 function invocations
  - **4 CPU-hrs Active CPU**
  - **360 GB-hrs provisioned memory**
  - 100 GB Fast Data Transfer
  - **10 GB Fast Origin Transfer**
  - 1,000,000 CDN requests
  - 100 deployments/day
  - 1,000,000 service requests (internal binding calls only)

  Source: https://vercel.com/docs/plans/hobby and https://vercel.com/docs/services/pricing
- **What happens when you exceed a limit:** "In most cases, if you exceed your usage limits on the Hobby plan, you will have to wait until 30 days have passed before you can use the feature again." This is the real risk before **15 Dec 2026**. https://vercel.com/docs/plans/hobby#hobby-billing-cycle
- **Budget math** (my estimate, NOT VERIFIED):
  - Memory: one 90 s SSE run on a 2 GB instance is about 0.05 GB-hr, so 360 GB-hr covers roughly 7,000 runs. Fluid compute can also pack concurrent requests onto one instance.
  - Active CPU counts only CPU time, not I/O waits. LLM calls are therefore nearly free. OR-Tools solves are not. At 20 CPU-s per run, 4 CPU-hrs is about 720 runs/month.
  - Mitigation: cap the solver time limit, and rate-limit `/api/recover`.
- **Services bandwidth:** "The bytes a service returns are billed as Fast Origin Transfer... whether the response is a static file or comes from a function." The static site therefore counts against the **10 GB** Origin quota, not only the 100 GB Data Transfer quota. This is fine for a demo. https://vercel.com/docs/services/pricing#data-transfer
- **Runtime logs:** Hobby keeps **1 hour** of runtime logs. https://vercel.com/docs/plans/hobby

## 2. Python runtime

- **Versions:** **3.12 (default)**, **3.13**, and **3.14**. Set the version through `requires-python` in `pyproject.toml`, a `.python-version` file, or `Pipfile.lock`. "Vercel uses Python 3.12 when your repository does not define a supported Python version." https://vercel.com/docs/functions/runtimes/python/python-version
  - Our pyproject has `requires-python = ">=3.13"`. Which exact version Vercel resolves from `>=3.13` (3.13 or 3.14) is NOT VERIFIED.
  - Recommendation: add `services/api/.python-version` containing `3.13` to pin it. How that file ranks against pyproject is NOT VERIFIED.
- **Dependencies:** "Define dependencies in `pyproject.toml` (with or without a `uv.lock`), `requirements.txt`, or a `Pipfile`." uv is supported with zero config (changelog: "Python package manager uv is now available for builds with zero configuration"). https://vercel.com/docs/functions/runtimes/python#dependencies
  - Whether the `[dependency-groups] dev` group (pytest, mypy, ruff) is skipped at install time is NOT VERIFIED. Those packages are small even if installed.
- **FastAPI zero-config entrypoints:**
  - `app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py`, or `asgi.py`
  - the same filenames inside `src/` or `app/`
  - `[tool.vercel] entrypoint = "module:var"` in pyproject
  - The file must define top-level `app`.
  - **Our `services/api/app/main.py` with `app` matches** (relative to the service root). https://vercel.com/docs/frameworks/backend/fastapi#exporting-the-fastapi-application
- **Monorepo:**
  - Setting **Root Directory = `services/api`** works for the API only. Root Directory docs say: "Your app will not be able to access files outside of that directory. You also cannot use `..`". A build command there **cannot** build `apps/web`. https://vercel.com/docs/builds/configure-a-build#root-directory
  - For both apps in one project, use **Services**:
    - Root Directory must be the **repo root**.
    - Framework preset must be **Services**.
    - "A project builds as services only when this setting is selected and a `services` key is present in `vercel.json`."

    Sources: https://vercel.com/docs/services, https://vercel.com/kb/guide/python-backend-on-vercel, https://vercel.com/kb/guide/vercel-services
  - `builds` is legacy ("We recommend against using this property").
- **Bundle size:** "The standard Python bundle size limit is **500 MB** uncompressed." Large Functions (beta) allow up to 5 GB on Fluid compute. "There is no automatic tree-shaking for Python." https://vercel.com/docs/functions/runtimes/python#controlling-what-gets-bundled and https://vercel.com/docs/functions/limitations#bundle-size-limits
  - Will numpy, pandas, ortools and protobuf fit? My estimate is roughly 200 to 300 MB uncompressed for linux wheels, so they should fit under 500 MB. NOT VERIFIED. The build log will show the real size.
- **`excludeFiles`:** add a glob under `functions.<entry>.excludeFiles` in vercel.json, for example `{tests/**,**/test_*.py}`. In Services mode, `functions` must sit **inside the service object**, not at the top level. https://vercel.com/docs/services#top-level-configuration-in-services-mode
  - The exact key inside a service (`"app/main.py"`, relative to the service root) is NOT VERIFIED.
  - Do **not** exclude `app/fixtures/**` if the runtime reads it.

## 3. Duration, memory, streaming, region

- **Max duration (Fluid compute):** Hobby is **300 s default and 300 s maximum**. A 90 s SSE fits **with no config**. The timeout covers "time spent processing the request and sending the response, including streamed responses". On timeout you get a 504 `FUNCTION_INVOCATION_TIMEOUT`. https://vercel.com/docs/functions/limitations#max-duration
  - "As of April 23, 2025, fluid compute is enabled by default for new projects." Toggle it in Settings → Functions, or with `"fluid": true`. https://vercel.com/docs/fluid-compute
  - Limits **without** Fluid compute (the legacy 10 s default / 60 s max on Hobby) are no longer in the current limits page: NOT VERIFIED. Keep Fluid ON.
- **Memory:** Hobby gets **2 GB / 1 vCPU** (default and maximum). With Fluid compute, memory cannot be set in vercel.json; it is a dashboard setting only. https://vercel.com/docs/functions/limitations#memory-size-limits and https://vercel.com/docs/project-configuration/vercel-json#functions
- **Streaming:** "Vercel Functions support streaming responses when using the Python runtime." It has been on by default since Jan 2025, and `VERCEL_FORCE_PYTHON_STREAMING` is no longer needed. https://vercel.com/docs/functions/runtimes/python#streaming, https://vercel.com/docs/functions/streaming-functions#streaming-python-functions, https://vercel.com/changelog/python-vercel-functions-now-have-streaming-enabled-by-default
  - FastAPI `StreamingResponse` with `text/event-stream` specifically is not shown in the docs: NOT VERIFIED, but it is standard ASGI streaming.
- **Region:** "Hobby plans can select any **single** region." The default is `iad1`. Set it with `"regions": ["fra1"]` in vercel.json, in Dashboard → Settings → Functions → Function Regions, or with `vercel --regions fra1`. https://vercel.com/docs/project-configuration/vercel-json#regions and https://vercel.com/docs/functions/configuring-functions/region
  - Whether top-level `regions` is accepted in Services mode is NOT VERIFIED. It is not in the list of keys forbidden at the top level. If the deploy rejects it, set the region in the dashboard instead.
  - Static files are served from every CDN region regardless.

## 4. Serving the static site alongside FastAPI

Options, in order of preference:

**A. Services (recommended).**
- The web service is `apps/web` with framework `nextjs`. Vercel runs `npm install` and `next build` there.
- The API service is `services/api`.
- Routing is first-match, and "Routing into a service is final", so `/api/*` never falls through to Next.
- "The service receives the original request path. `GET /api/users` reaches `my_backend` as `/api/users`, not `/users`." https://vercel.com/docs/services/routing
- Next.js `output: "export"` inside a Vercel Next.js service is not documented by Vercel: NOT VERIFIED. Next.js lists Vercel static-export support as "Limited", meaning no server features, which we don't use. Expect it to be served as static files; check after the first deploy.
- Fallback if needed: `"framework": null, "buildCommand": "npm run build", "outputDirectory": "out"` on the web service (keys exist in the service config reference: https://vercel.com/docs/services/config-reference). Whether a frameworkless static service works is NOT VERIFIED.

**B. FastAPI-only project with `public/`.** For FastAPI projects, `public/` at the project root is served from the CDN ("Do not mount the `public/` directory with `app.mount()`"). https://vercel.com/docs/frameworks/backend/fastapi#the-public-directory
- With Root Directory = `services/api`, the build cannot reach `../../apps/web` (see section 2).
- Making this work requires committing a prebuilt copy of `out/` into `services/api/public/`, which is a repo change. Whether a `public/` dir created *during* a build command is picked up is NOT VERIFIED.

**C. FastAPI `app.mount(StaticFiles)`.** Vercel promotes `StaticFiles` mounts and `app.frontend()` to the CDN at build time. However, it keeps them in the function when there is **top-level middleware**, and our `main.py` has CORS and `@app.middleware("http")`. https://vercel.com/docs/frameworks/backend/fastapi#middleware
- **Leave `STATIC_DIR` unset on Vercel**, so the "/" mount never activates.

**Recommended vercel.json (repo root)** with confidence per part:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "regions": ["fra1"],
  "services": {
    "api": { "root": "services/api/", "framework": "fastapi", "entrypoint": "app.main:app" },
    "web": { "root": "apps/web/", "framework": "nextjs" }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "api" } },
    { "source": "/(.*)", "destination": { "service": "web" } }
  ]
}
```

- `services` + `root` + `entrypoint: "app.main:app"` + `framework`: **high**. This is the same shape as the official KB example (`"backend": {"root": "backend/", "framework": "fastapi", "entrypoint": "app.main:app"}`).
- `rewrites` with `{ "service": ... }` destinations and path preservation: **high** (from the docs).
- `regions` at the top level in Services mode: **medium**. The dashboard setting is a safe alternative.
- Next static export as a `nextjs` service: **medium** (NOT VERIFIED).
- No `maxDuration` needed, since the Hobby default is already 300 s: **high**.
- Optional, **low** confidence on the key: inside `"api"` add `"functions": { "app/main.py": { "excludeFiles": "tests/**" } }`.
- Suggested file-layout changes: add `services/api/.python-version` (`3.13`). No `api/index.py` shim is needed.

## 5. Env vars, CLI and logs

- **Environment variables:**
  - Dashboard: Project → Settings → Environment Variables. Choose Production, Preview and/or Development, and Config or Secret.
  - "Any change you make to environment variables are not applied to previous deployments, they only apply to new deployments", so **redeploy after changes**.
  - The limit is 64 KB total per deployment. https://vercel.com/docs/environment-variables
- **CLI for env vars:**
  - `vercel env add NEBIUS_API_KEY production`. It prompts for the value. Production and Preview default to the Secret type, and `--sensitive` forces it.
  - Also: `vercel env ls`, `vercel env pull .env.local`, `vercel env update`, `vercel env rm`.
  - Avoid `echo value |` piping for secrets, because it lands in shell history.

  https://vercel.com/docs/cli/env
- **Deploy flow**, run from the **repo root**, not a subdirectory:
  1. `npm i -g vercel`
  2. `vercel login` (https://vercel.com/docs/cli/login)
  3. `vercel link`, or `vercel link --repo` for monorepos (https://vercel.com/docs/monorepos)
  4. `vercel project update --framework services` (from the KB guide)
  5. `vercel` for a preview. Note: "The first deployment of a new project is always a production deployment."
  6. `vercel --prod` for later production deploys (https://vercel.com/docs/cli/deploy)

  Useful flags: `--logs` prints build logs, and `--archive=tgz` helps if the upload has thousands of files. Make sure `node_modules`, `out`, `.venv` and `test-results` are not uploaded. Gitignored files are skipped by default, which is NOT VERIFIED; use a `.vercelignore` otherwise.
- **Logs:**
  - `vercel logs` shows the last 30 min, 100 records.
  - `vercel logs --environment production --query 'level:error' --since 1h`
  - `vercel logs requests --query 'httpStatus >= 500'`
  - `--follow` is deprecated.
  - Dashboard → project → Logs. Hobby keeps 1 h of runtime logs. https://vercel.com/docs/cli/logs
- **Smoke test:** `vercel curl /api/health --deployment <preview-url>` bypasses Deployment Protection on previews (https://vercel.com/kb/guide/python-backend-on-vercel). Give judges the **production** `*.vercel.app` domain, not a per-deployment URL, which may be behind Vercel Authentication. Default protection scope is NOT VERIFIED.

## 6. Pitfalls

- **Cold start:**
  - Python imports of OR-Tools, numpy and pandas add seconds on a cold start (NOT VERIFIED magnitude).
  - Vercel precompiles `.pyc` and pre-warms production deployments on Fluid compute (https://vercel.com/docs/functions/runtimes/python#controlling-what-gets-bundled, https://vercel.com/docs/fluid-compute).
  - Functions not invoked for **2 weeks (prod)** or 48 h (preview) are archived, and the next call adds 1 s or more (https://vercel.com/docs/functions/runtimes#archiving).
  - Hit `/api/health` before judging sessions.
- **Filesystem:** "read-only filesystem with writable `/tmp` scratch space up to 500 MB". There is no persistence between instances, so keep state in memory per request or in external storage. Relative `open()` resolves from the project base, not from the file's directory. https://vercel.com/docs/functions/runtimes#file-system-support and https://vercel.com/docs/functions/runtimes/python#reading-relative-files
- **Body size:** "The maximum payload size for the request body or the response body of a Vercel Function is **4.5 MB**" (413 `FUNCTION_PAYLOAD_TOO_LARGE`). Whether long-lived streamed responses are exempt is NOT VERIFIED. Our SSE payloads are small. https://vercel.com/docs/functions/limitations#request-body-size
- **SSE buffering:** no Vercel doc covers proxy buffering for `text/event-stream` (NOT VERIFIED). Defensive steps:
  - Send `Cache-Control: no-cache, no-transform` and `X-Accel-Buffering: no`.
  - Don't add GZip middleware to the SSE route.
  - Emit `: ping` comments every ~15 s.
  - Flush the first byte quickly.
  - The client should handle a 504 at 300 s and reconnect.
- **Lifespan:** FastAPI lifespan is supported, but shutdown cleanup gets at most **500 ms** after SIGTERM. https://vercel.com/docs/frameworks/backend/fastapi#startup-and-shutdown
- **Concurrency:** Fluid compute runs several requests in one Python process ("optimized concurrency"). Module-level mutable state is shared between concurrent requests, so keep per-run state request-scoped. https://vercel.com/docs/fluid-compute#optimized-concurrency
- **CORS:** same origin under Services, so `CORS_ORIGINS` can stay empty in production.
- **Services is Beta:** config may change before 15 Dec. Freeze the working deployment and avoid re-deploying near the deadline unless needed. Instant rollback is available in the dashboard (NOT VERIFIED for Services specifically).
