"use client";

import type { AgentEvent } from "@/lib/api/sse";
import { RUN_PHASES, runProgress, type RunPhase } from "@/lib/run";

const PHASE_TEXT: Record<string, string> = {
  perceive: "Reading the situation",
  diagnose: "Diagnosing the delay",
  plan: "Weighing permitted fixes",
  verify: "Verifying a proposal",
  revise: "Revising after verifier feedback",
  present: "Presenting options",
};

const STEP_TEXT: Record<RunPhase, string> = {
  perceive: "Read the situation",
  diagnose: "Diagnose the delay",
  plan: "Weigh permitted fixes",
  verify: "Verify with the solver",
  revise: "Revise after a rejection",
  present: "Present verified options",
};

function TraceRow({ event }: { event: AgentEvent }) {
  const d = event.data as Record<string, unknown>;
  const t = `${(event.at_ms / 1000).toFixed(1)}s`;
  switch (event.type) {
    case "phase":
      return <li className="pt-2 text-xs font-semibold text-porcelain">{PHASE_TEXT[String(d.name)] ?? String(d.name)}</li>;
    case "model_call": {
      const usage = d.usage as { total_tokens?: number } | undefined;
      const rid = d.request_id ? String(d.request_id).slice(0, 10) : null;
      const real = Boolean(rid) || Number(d.latency_ms) > 0;
      return (
        <li className="text-xs text-focus">
          <span className="text-faint">{t} </span>
          {real
            ? `Model call ${String(d.n)}: ${((Number(d.latency_ms) || 0) / 1000).toFixed(1)}s${usage?.total_tokens ? `, ${usage.total_tokens.toLocaleString("en")} tokens` : ""}${rid ? `, request ${rid}` : ""}`
            : `Scripted step ${String(d.n)}`}
        </li>
      );
    }
    case "tool_result":
      return (
        <li className={`text-xs ${d.ok ? "text-muted" : "text-amber"}`}>
          <span className="text-faint">{t} </span>
          <code className="text-porcelain">{String(d.name)}</code> {String(d.summary)}
        </li>
      );
    case "error":
      return <li className="text-xs font-semibold text-coral">{String(d.message)}</li>;
    case "done":
      return (
        <li className="pt-1 text-xs text-faint">
          Finished in {((Number(d.elapsed_ms) || 0) / 1000).toFixed(1)}s: {String(d.model_calls)} model calls, {String(d.evaluations)} verifier checks.
        </li>
      );
    default:
      return null;
  }
}

/** The full step-by-step trace, exactly as the server streamed it. */
export function AgentTrace({ events, running, label, open }: { events: AgentEvent[]; running: boolean; label: string; open?: boolean }) {
  const tools = events.filter((e) => e.type === "tool_result").length;
  return (
    <details open={open} className="rounded-xl border border-line bg-panel p-3" aria-live={running ? "polite" : undefined}>
      <summary className="cursor-pointer text-sm font-semibold">
        {label}{" "}
        <span className="ml-1 text-xs font-normal text-muted">
          {running ? `every step so far (${tools} tool calls)` : `${tools} tool calls`}
        </span>
      </summary>
      <ol className="mt-1 max-h-56 space-y-1 overflow-y-auto pr-1">
        {events.map((e) => (
          <TraceRow key={e.seq} event={e} />
        ))}
        {running && <li className="heartbeat text-xs text-focus">Waiting for the next step…</li>}
      </ol>
    </details>
  );
}

/**
 * The agent at work: which step of its loop it is on, what it just did, and what the verifier
 * has said so far. Built only from the events the server has streamed.
 */
export function AgentRun({ events, label, live, onStop }: { events: AgentEvent[]; label: string; live: boolean; onStop: () => void }) {
  const p = runProgress(events);
  const heading = p.current ? (PHASE_TEXT[p.current] ?? p.current) : "Starting the run";
  const unit = live ? "model call" : "scripted step";
  const furthest = Math.max(-1, ...RUN_PHASES.map((ph, i) => (p.visited.has(ph) ? i : -1)));
  return (
    <section aria-labelledby="run-h" className="rounded-xl border border-focus/45 bg-[#0f1726] p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0" aria-live="polite">
          <p className="flex items-center gap-1.5 text-xs text-focus">
            <span aria-hidden className="heartbeat h-2 w-2 shrink-0 rounded-full bg-focus" />
            {label} is working{p.steps > 0 ? `, ${unit} ${p.steps}` : ""}
          </p>
          <h3 id="run-h" className="mt-1 font-display text-2xl leading-tight font-bold">
            {heading}
            <span aria-hidden className="heartbeat">…</span>
          </h3>
        </div>
        <button type="button" onClick={onStop} className="min-h-10 shrink-0 rounded-md border border-line-strong px-3 text-xs font-semibold hover:border-porcelain">
          Stop
        </button>
      </div>

      {p.latest && (
        <p className={`mt-1 truncate text-xs ${p.latest.ok ? "text-muted" : "text-amber"}`} title={`${p.latest.name}: ${p.latest.summary}`}>
          <span className="text-faint">Last: </span>
          <code className="text-porcelain">{p.latest.name}</code> {p.latest.summary}
        </p>
      )}

      <ol className="mt-3 space-y-1.5" aria-label="Agent steps">
        {RUN_PHASES.map((phase, i) => {
          const now = p.current === phase;
          const seen = p.visited.has(phase);
          const skipped = !seen && i < furthest;
          const detail =
            phase === "verify" && p.checked > 0 ? `${p.checked} checked, ${p.holds} hold` : skipped ? "skipped" : null;
          return (
            <li key={phase} aria-current={now ? "step" : undefined} className={`flex items-center gap-2.5 text-[13px] ${now ? "font-bold text-porcelain" : seen ? "text-muted" : "text-faint"}`}>
              <span
                aria-hidden
                className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] leading-none ${now ? "step-live border-2 border-focus" : seen ? "bg-line-strong text-porcelain" : "border border-dashed border-line-strong"}`}
              >
                {now ? <span className="h-2 w-2 rounded-full bg-focus" /> : seen ? "✓" : ""}
              </span>
              <span className="min-w-0 flex-1">
                {STEP_TEXT[phase]}
                <span className="sr-only">{now ? " (now)" : seen ? " (done)" : skipped ? "" : " (not yet)"}</span>
              </span>
              {detail && <span className="shrink-0 text-xs font-normal text-muted tabular-nums">{detail}</span>}
            </li>
          );
        })}
      </ol>
      <p className="mt-3 text-[11px] leading-snug text-faint">
        {live ? "The model proposes; nothing changes until the solver verifies a fix and you apply it." : "Simulated agent: no model is called. Every proposal is still checked by the solver."}
      </p>
    </section>
  );
}
