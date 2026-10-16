# Ripple Room: free hosting research for the judge demo

Research date: 16 Oct 2026. All URLs were accessed on 2026-10-16. "NOT VERIFIED" means I found no primary-source confirmation.

## 0. Requirements and hard dates

- The demo must stay publicly reachable and free **until 15 Dec 2026 12:00 PT**, when the judging period ends. The rule says: "The Entrant must make the Project available free of charge and without any restriction, for testing, evaluation and use by the Sponsor, Administrator and Judges until the Judging Period ends." Source: https://nebiusglobalaihackathon.devpost.com/rules
- Workload:
  - static or Next.js frontend
  - Python FastAPI backend with OR-Tools (wheel about 30 MB), needing about 512 MB RAM
  - agent runs of 60 to 90 s streamed over SSE
  - outbound calls to the Nebius Token Factory API
- The owner wants no credit card and no spend.

## 1. Comparison matrix

| Platform | Card needed? | RAM / CPU (free) | Sleep / cold start | Request limit | SSE / streaming | Persistence | Risk before 15 Dec 2026 |
|---|---|---|---|---|---|---|---|
| **Vercel Hobby** (Next.js + Python Functions) | No (Hobby is free; no card found in docs) | Functions: **2 GB / 1 vCPU** | Serverless. Cold start on first hit; Python import time for OR-Tools is NOT VERIFIED | **300 s default and max** (Hobby) | Yes. "Vercel Functions support streaming responses when using the Python runtime" | None in-function. Instances are ephemeral and state is not shared | Low. Watch the monthly allotments (4 h Active CPU, 360 GB-hrs memory, 1M invocations). Hobby is non-commercial only (a hackathon demo is fine) |
| **Render Free web service** | Docs don't require one. Community reports say card verification ($1 reversed) is sometimes requested | **512 MB / 0.1 CPU** | Spins down after **15 min** idle; about **1 min** to wake | About 100 min per community/staff posts (NOT VERIFIED in official docs) | Works per staff; one forum report of an SSE drop at 60 s was unresolved | Ephemeral FS; "might restart a Free web service at any time" | Medium. 750 h/month is enough for one service. **5 GB/month bandwidth** under the Aug 2026 plans; without a card, overage suspends all free services for the month |
| **Hugging Face Spaces** (Docker, CPU Basic) | **PRO needed ($9/mo)** for Docker or Gradio on CPU Basic | 16 GB / 2 vCPU (but paid gate) | Sleeps when unused (free hardware) | n/a | n/a | Ephemeral unless you attach a Storage Bucket | **Excluded.** Docs now say: "Gradio and Docker Spaces run on compute and require a paid plan to create". Static Spaces are still free |
| HF Spaces: Gradio on ZeroGPU | No (2 free Spaces; account must be at least 30 days old with a verified email) | Not documented for the CPU side | Sleeps when unused | n/a | Custom FastAPI routes and SSE inside a Gradio app on ZeroGPU: NOT VERIFIED | Ephemeral | High: hacky, Gradio-only. Last resort only |
| **Koyeb Free** | **Yes**: "We require a credit card", plus a $29 pre-auth hold | 512 MB / 0.1 vCPU / 2 GB SSD, 1 per org, Frankfurt or Washington DC | Scales to zero after **1 h** without traffic | NOT VERIFIED | NOT VERIFIED | No volumes | Violates the no-card preference. Mistral agreed to acquire Koyeb (Feb 2026, per third-party sources) |
| **Fly.io** | Trial has no card; **card required after trial** | n/a | n/a | n/a | n/a | n/a | **Excluded.** "New organizations don't have a free tier"; the trial is 2 h machine runtime or 7 days |
| **Railway** | Trial card requirement NOT VERIFIED; Railway "requires the use of a post-paid card" for paid usage | Trial: 1 GB, shared vCPU. Free plan: 0.5 GB / 1 vCPU | Not documented on these pages | NOT VERIFIED | NOT VERIFIED | Volumes (paid) | High. The $5 trial lasts 30 days, then **$1/month credit**, which can't keep a 0.5 GB service up all month (NOT VERIFIED math) |
| **Google Cloud Run** | **Billing account required**, which in practice means a card or other payment method | Generous (180k vCPU-s, 360k GiB-s, 2M req/mo) | Scale to zero; cold start | Configurable (long) | Yes | Ephemeral | Violates no-card. Also a spend risk if abused |
| **Netlify** | NOT VERIFIED | Functions: JS/TS/Go. **Python not supported** per secondary sources (NOT VERIFIED officially) | n/a | Sync functions about 60 s per 2026 secondary sources (NOT VERIFIED) | n/a | n/a | Frontend-only candidate |
| **Cloudflare Pages / Workers** | No for the Free plan | Workers Free: **128 MB, 10 ms CPU per request** | None (isolates) | No wall-clock limit for HTTP | Yes | KV/D1 | Python Workers support only "pure and PyEmscripten" or Pyodide packages, so OR-Tools native wheels won't run (inference). **Containers are not on the Free plan** (Workers Paid, $5). Frontend-only candidate |
| **Deno Deploy** | NOT VERIFIED | JS/TS only ("serverless platform for running JavaScript and TypeScript") | n/a | n/a | n/a | n/a | Frontend-only; no Python |
| **Oracle Cloud Always Free** | **Card required** for verification (secondary sources; Oracle FAQ returned 403, so NOT VERIFIED from Oracle) | A1 Arm: "2 OCPUs and 12 GB" total; or 2 x E2.1.Micro (1/8 OCPU, 1 GB) | Always on (a VM) | None | Yes (your own server) | Block storage | **Idle reclamation**: "CPU utilization for the 95th percentile is less than 20%" over 7 days (and network and memory below 20%). A judge-only demo VM will look idle and may be reclaimed before 15 Dec |

### Sources (all accessed 2026-10-16)
- Vercel limits: https://vercel.com/docs/functions/limitations (updated 2026-08-24). Quotes: "Hobby: 300s default and maximum", "Hobby 2 GB / 1 vCPU", "500 MB for Python".
- Vercel Python: https://vercel.com/docs/functions/runtimes/python ("Python on Vercel is now generally available"; Python 3.12 default, 3.13 and 3.14 available; streaming supported).
- Vercel FastAPI: https://vercel.com/docs/frameworks/backend/fastapi. It covers `app.frontend("/", directory="dist")` and StaticFiles being "promoted to the CDN at build time", plus lifespan support.
- Vercel Hobby allotments and commercial-use rule: https://vercel.com/docs/limits/fair-use-guidelines (updated 2026-09-14). Hobby includes 1,000,000 invocations, 4 h Active CPU, 360 GB-hrs provisioned memory, and 100 GB Fast Data Transfer.
- Vercel CDN origin timeout for external rewrites: https://vercel.com/changelog/cdn-origin-timeout-increased-to-two-minutes. The limit is 120 s to first byte, then data must arrive "at least once every 120 seconds".
- Render free: https://render.com/docs/free ("spins down a Free web service that goes 15 minutes without receiving any inbound traffic"; "750 Free instance hours"). Render specs: https://render.com/docs/compute-plans ("0.1 CPU", "512 MB").
- Render plan change: third-party summary at https://jwatte.com/blog/render-com-platform-review.md, citing https://render.com/docs/new-workspace-plans. Free bandwidth was cut from 100 GB to 5 GB. I did not re-check the 5 GB figure on Render's own pages.
- Render timeout and card reports (community, undated): https://community.render.com/t/need-to-increase-requests-timeout-of-5-minutes/4001, https://community.render.com/t/server-sent-events-connection-closes-after-one-minute/4597, https://community.render.com/t/im-not-able-to-deploy-a-web-service/22191
- HF: https://huggingface.co/docs/hub/spaces-overview, https://huggingface.co/docs/hub/spaces-zerogpu, https://huggingface.co/pricing (PRO $9/mo, "Host your own ZeroGPU, Gradio & Docker Spaces on compute"). User reports of the change dated 8 to 24 July 2026: https://discuss.huggingface.co/t/docker-sdk-now-marked-as-paid-when-creating-a-new-space/177580
- Koyeb: https://www.koyeb.com/docs/reference/instances, https://www.koyeb.com/docs/faqs/pricing
- Fly.io: https://docs.fly.io/about/pricing. Railway: https://docs.railway.com/reference/pricing/free-trial and https://docs.railway.com/reference/pricing/plans
- Cloud Run: https://docs.cloud.google.com/free/docs/free-cloud-features ("A Google Cloud billing account is required to access the Google Cloud Free Tier").
- Cloudflare: https://developers.cloudflare.com/workers/platform/limits/, https://developers.cloudflare.com/workers/languages/python/packages/, https://developers.cloudflare.com/containers/pricing/
- Deno: https://docs.deno.com/deploy/. Oracle: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- GitHub cron caveat: https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/disabling-and-enabling-a-workflow ("In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days").

## 2. Key findings

1. **Hugging Face Docker Spaces are no longer free.** I expected this to be the default choice, but the docs and pricing now gate Docker and Gradio on CPU Basic behind PRO. User reports start 8 July 2026, and HF has made no announcement.
2. **Vercel Hobby can now run the whole stack with no card.** Python is GA with FastAPI zero-config. A function gets 2 GB / 1 vCPU and up to 300 s, which covers a 90 s streamed agent run. The bundle limit is 500 MB, so a 30 MB OR-Tools wheel fits. Agent waits on Token Factory are I/O, and "Waiting for I/O (e.g. calling AI models...) does not count towards active CPU time".
3. **Render Free is the only credible no-card always-on container.** It is weak, though: 0.1 CPU makes CP-SAT slow, 512 MB is tight with OR-Tools, and it has 1 min cold starts.
4. Koyeb, Cloud Run, Oracle, and Fly all need a card. Oracle also reclaims idle VMs, which is a real threat for a judge-only demo.

## 3. Recommended topology

### Primary: Vercel Hobby, one project, no card
- **Frontend:** Next.js `output: 'export'` (static), served from Vercel's CDN.
- **Backend:** FastAPI as a Vercel Python Function, in the same project via Vercel Services (https://vercel.com/kb/guide/python-backend-on-vercel), or in a FastAPI-first layout with `app.frontend("/", directory="out")`. Same origin means no CORS.
- **Set `maxDuration: 300`** for the agent endpoint and keep CP-SAT `max_time_in_seconds` small (e.g. 2 to 5 s per verify).
- **Design rules this platform forces. These are required, not optional:**
  - **Stateless backend.** Requests can hit different instances, and in-memory dicts are lost. The client sends the full plan, disruption, and patch in each request, and the client holds Apply/Undo history (e.g. localStorage plus a URL-encoded scenario id for seeded demos).
  - **Do the agent run inside a single streaming request.** Use `POST /api/agent/run` returning `text/event-stream` and read it with `fetch()` plus a ReadableStream. Do **not** use "start background task, then poll or GET EventSource", because a background task cannot outlive the response on serverless.
  - Emit an SSE heartbeat comment every 10 to 15 s so proxies don't idle-cut the stream.
- **Single-container question:** on Vercel this is effectively achieved without a container, since FastAPI can serve the pre-built static export (`app.frontend` / StaticFiles get promoted to the CDN). That is sensible. A literal Dockerfile is not how Vercel runs Python. Keep the Dockerfile anyway for the fallback.

### Fallback: Render Free web service, one Docker container
- FastAPI serves the static export (StaticFiles at `/`) and `/api/*`, all from one container on one URL. This is a sensible, simple setup here: there is no CORS, it is one deploy, and the same image runs locally.
- Point a second domain or path at it from the README ("If the primary is down, use ...").
- Mitigate the cold start with a "waking the solver..." UI state. Optionally use a keep-warm ping (an external free uptime monitor; GitHub Actions cron only works while the repo has activity within 60 days).
- Optional: the Vercel-hosted frontend can call Render directly via CORS when the Vercel function quota is exhausted. Use a runtime-configurable API base URL.

### Third line: an offline replay mode, in the same frontend
- Ship 2 or 3 **pre-recorded agent runs** (JSON event logs, with CP-SAT verdicts included) that the UI can replay through the same SSE renderer.
- Use it automatically when the backend or the Token Factory key fails, and label it clearly as "Replay (recorded <date>)". This also protects against Token Factory credit exhaustion or key expiry before 15 Dec. Credit validity for the Nebius Builder Program is NOT VERIFIED.

## 4. Exact risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| OR-Tools wheel fails to import on Vercel's Python runtime (manylinux/glibc), or the cold import is slow | Unknown (NOT VERIFIED) | **Smoke-deploy a hello-world `import ortools; solve tiny model` to Vercel on day 1.** Pin the Python version (3.12) and the ortools version. Measure cold start. |
| Function exceeds 300 s | Low (runs take 60 to 90 s) | Put a hard 150 s budget on the agent loop. Stream partial results. Cap the number of proposals. |
| Hobby allotments exhausted by abuse (Active CPU 4 h, provisioned memory 360 GB-hrs; one 90 s run at 2 GB is about 0.05 GB-hr, so roughly 7k runs/mo; my estimate) | Low to medium | Per-IP rate limit, a cap on runs per day, and a solver time limit. Replay mode as the fallback. |
| Public Token Factory key gets drained by anonymous users | Medium | Keep the key server-side only (Vercel env var). Rate limit. Cap tokens per run. Use cheaper Nemotron Nano or Super for the bulk and Ultra for one call. Replay fallback. |
| Hobby "non-commercial" clause | Low | A hackathon demo with no payments or ads is non-commercial per Vercel's definition. |
| Render: card prompt, 0.1 CPU timeouts, 5 GB bandwidth, random restarts | Medium | Fallback only. Keep static assets on Vercel/CDN so Render bandwidth covers only API calls. |
| Platform terms change before 15 Dec (as happened with HF in July 2026 and Render in Aug 2026) | Medium | Two independent providers plus replay mode. Re-check both URLs weekly from 1 Dec. Have a pre-submission checklist. |
| Can't edit the submission after 30 Oct if the URL changes | Medium | Put one stable URL in the submission and the README. Make the README's "Live demo" section list the primary, the fallback, and replay instructions. |

Bottom line: use **Vercel Hobby (Next.js static export + FastAPI Python Function, same origin, stateless, single-request SSE)** as the primary, **Render Free (one Docker container: FastAPI + static export)** as the fallback, and keep **recorded-run replay** as the last line. All three need no card. Do not plan on HF Docker Spaces, Koyeb, Fly.io, Cloud Run, or Oracle.
