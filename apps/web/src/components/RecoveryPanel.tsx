"use client";

import { useState } from "react";
import type { AgentEvent } from "@/lib/api/sse";
import type { Evaluation, Health, RevisionView } from "@/lib/api/types";
import { clock, delta, eur } from "@/lib/format";
import { touchedTasks, type RoomView } from "@/lib/viewmodel";
import type { Phase, RecoveryOption, RoomState } from "@/state/room";

const PRIORITY_CHIPS = [
  "Keep extra spend at zero.",
  "Protect the guest experience; spending is fine.",
  "Change as little of the crew plan as possible.",
];

const PHASE_TEXT: Record<string, string> = {
  perceive: "Reading the situation",
  diagnose: "Diagnosing the delay",
  plan: "Weighing permitted fixes",
  verify: "Verifying a candidate",
  revise: "Revising after verifier feedback",
  present: "Presenting options",
};

const SOURCE_TEXT: Record<RecoveryOption["source"], string> = {
  nemotron: "Proposed by Nemotron",
  mock: "Simulated agent",
  search: "Solver search, no AI",
};

function modelName(id: string): string {
  const m = id.split("/").pop() ?? id;
  if (/super/i.test(m)) return "Nemotron 3 Super";
  if (/ultra/i.test(m)) return "Nemotron 3 Ultra";
  if (/lightning/i.test(m)) return "Nemotron 3.5 Lightning";
  if (/nano/i.test(m)) return "Nemotron Nano";
  return m;
}

export function AiBadge({ health }: { health: Health | null }) {
  if (!health) return <span className="text-xs text-faint">AI status unknown</span>;
  const live = health.ai.mode === "live";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${live ? "border-focus/50 text-focus" : "border-line text-muted"}`}>
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${live ? "heartbeat bg-focus" : "bg-faint"}`} />
      {live ? `${modelName(health.ai.planner_model)} on Nebius Token Factory` : "Simulated agent, no model calls"}
    </span>
  );
}

function verdict(ev: Evaluation): { text: string; tone: string } {
  switch (ev.status) {
    case "verified":
      return { text: "Verified", tone: "text-signal border-signal/40" };
    case "infeasible":
      return { text: "Does not fit", tone: "text-coral border-coral/40" };
    case "rejected":
      return { text: "Rejected", tone: "text-coral border-coral/40" };
    default:
      return { text: "Unproven (timeout)", tone: "text-amber border-amber/40" };
  }
}

function reasonOf(ev: Evaluation): string | null {
  if (ev.violations.length) return ev.violations[0]?.message ?? null;
  if (ev.infeasibility) {
    const best = ev.infeasibility.best_readiness;
    return best != null ? `Best possible with this patch: ready ${clock(best)} (${delta(ev.infeasibility.best_delta)}).` : (ev.infeasibility.reasons[0] ?? null);
  }
  return null;
}

function TraceRow({ event }: { event: AgentEvent }) {
  const d = event.data as Record<string, unknown>;
  const t = `${(event.at_ms / 1000).toFixed(1)}s`;
  switch (event.type) {
    case "phase":
      return (
        <li className="pt-2 text-xs font-semibold text-porcelain">
          {PHASE_TEXT[String(d.name)] ?? String(d.name)}
        </li>
      );
    case "model_call": {
      const usage = d.usage as { total_tokens?: number } | undefined;
      const rid = d.request_id ? String(d.request_id).slice(0, 10) : null;
      return (
        <li className="text-xs text-focus">
          <span className="text-faint">{t} </span>
          {d.request_id || Number(d.latency_ms) > 0 ? `Model call ${String(d.n)}: ${((Number(d.latency_ms) || 0) / 1000).toFixed(1)}s` : `Scripted step ${String(d.n)}`}
          {usage?.total_tokens ? `, ${usage.total_tokens.toLocaleString("en")} tokens` : ""}
          {rid ? `, request ${rid}` : ""}
          {typeof d.reasoning_excerpt === "string" && (
            <details className="mt-1 text-muted">
              <summary className="cursor-pointer">Model reasoning (excerpt)</summary>
              <p className="mt-1 whitespace-pre-wrap">{d.reasoning_excerpt}</p>
            </details>
          )}
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
    case "candidate": {
      const ev = d.evaluation as Evaluation;
      const v = verdict(ev);
      const reason = reasonOf(ev);
      return (
        <li className="text-xs">
          <span className={`mr-1.5 rounded border px-1.5 py-px font-semibold ${v.tone}`}>
            {String(d.candidate_id)} {v.text}
          </span>
          <span className="text-muted">{String(d.rationale ?? "")}</span>
          {reason && <span className="block pl-1 text-coral/90">{reason}</span>}
        </li>
      );
    }
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

function OptionCard({
  option,
  selected,
  onPreview,
  onApply,
  applying,
  current,
}: {
  current: RevisionView;
  option: RecoveryOption;
  selected: boolean;
  onPreview: () => void;
  onApply: () => void;
  applying: boolean;
}) {
  const ev = option.evaluation;
  const ready = ev.schedule?.readiness;
  const spare = ev.schedule?.deadline_delta != null ? -ev.schedule.deadline_delta : null;
  const impacts = ev.service_impacts.map((s) => s.text);
  return (
    <li>
      <article className={`rounded-xl border p-3 transition-colors ${selected ? "border-focus bg-[#121b2a]" : "border-line bg-panel"}`}>
        <button type="button" onClick={onPreview} aria-pressed={selected} className="w-full text-left">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-[15px] leading-snug font-bold">{option.title}</h3>
            <span className="shrink-0 rounded border border-signal/40 px-1.5 py-px text-[11px] font-semibold text-signal">Verified</span>
          </div>
          <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
            <div>
              <dt className="text-faint">Ready</dt>
              <dd className="font-display text-xl font-bold">{ready != null ? clock(ready) : "—"}</dd>
              <dd className="text-muted">{spare != null ? (spare === 0 ? "no margin" : `${spare} min spare`) : ""}</dd>
            </div>
            <div>
              <dt className="text-faint">Extra cost</dt>
              <dd className="font-display text-xl font-bold">{eur(ev.cost_cents)}</dd>
            </div>
            <div>
              <dt className="text-faint">Tasks touched</dt>
              <dd className="font-display text-xl font-bold">{touchedTasks(ev, current).length}</dd>
            </div>
          </dl>
          <p className={`mt-2 text-xs ${impacts.length ? "text-amber" : "text-muted"}`}>
            {impacts.length ? `Guest-facing trade-off: ${impacts.join("; ")}` : "No guest-facing trade-off."}
          </p>
          {option.why && (
            <p className="mt-2 border-l-2 border-focus/50 pl-2 text-xs text-muted">
              <span className="text-focus">{option.source === "nemotron" ? "Nemotron: " : "Agent note: "}</span>
              {option.why}
            </p>
          )}
          <p className="mt-2 text-[11px] text-faint">
            {SOURCE_TEXT[option.source]}. Checked by CP-SAT ({ev.solver.status === "OPTIMAL" ? "least disruptive timing for this fix, proven" : "feasible, not proven least disruptive"}, {ev.solver.wall_ms} ms).
          </p>
        </button>
        {selected && (
          <button
            type="button"
            onClick={onApply}
            disabled={applying}
            className="mt-3 w-full rounded-lg bg-signal px-3 py-2 text-sm font-bold text-[var(--signal-ink)] hover:brightness-110 disabled:opacity-60"
          >
            {applying ? "Applying…" : "Apply this plan"}
          </button>
        )}
      </article>
    </li>
  );
}

interface PanelProps {
  current: RevisionView;
  phase: Phase;
  state: RoomState;
  room: RoomView;
  impactCounts: { delayed: number; atRisk: number; breach: number; blocked: number } | null;
  onRecover: (priorities: string) => void;
  onCancel: () => void;
  onSearch: () => void;
  onPreview: (id: string | null) => void;
  onApply: (option: RecoveryOption) => void;
  onUndo: () => void;
}

export function RecoveryPanel({ current, phase, state, room, impactCounts, onRecover, onCancel, onSearch, onPreview, onApply, onUndo }: PanelProps) {
  const [priorities, setPriorities] = useState("");
  const run = state.run;
  const live = state.health?.ai.mode === "live";
  const runnable = phase === "impact" || (phase === "options" && run.status !== "running" && run.options.length === 0);
  const [showForm, setShowForm] = useState(false);
  const late = room.mode !== "preview" && room.deadlineDelta != null && room.deadlineDelta > 0;

  if (phase === "ready" || phase === "applied") {
    return (
      <section aria-labelledby="rec-h" className="space-y-3">
        <h2 id="rec-h" className="font-display text-2xl font-bold">
          {phase === "applied" ? "Recovery applied" : "The plan holds"}
        </h2>
        {phase === "applied" && (
          <div className="rounded-xl border border-signal/40 bg-panel p-3 text-sm">
            <p>
              <span className="font-semibold text-signal">{state.lastAppliedTitle ?? "Option"}</span> is now the working plan, re-verified by the server.
            </p>
            <button type="button" onClick={onUndo} className="mt-2 rounded-md border border-line px-3 py-1.5 text-xs hover:border-porcelain">
              Undo
            </button>
          </div>
        )}
        <div className="rounded-xl border border-line bg-panel p-3 text-sm">
          <h3 className="font-semibold">What sets the doors time</h3>
          <ol className="mt-2 space-y-1 text-muted">
            {room.drivingPath
              .filter((id) => !room.byId[id]?.milestone || id === room.drivingPath[0])
              .map((id) => (
                <li key={id} className="flex justify-between gap-2">
                  <span>{room.byId[id]?.label}</span>
                  <span className="text-faint">{room.byId[id]?.start != null ? clock(room.byId[id]!.start!) : ""}</span>
                </li>
              ))}
          </ol>
          <p className="mt-2 text-xs text-faint">Any delay on this chain moves the doors. Try an incident on the left.</p>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="rec-h" className="space-y-3">
      <h2 id="rec-h" className="font-display text-2xl font-bold">
        {late ? `Doors ${room.deadlineDelta} min late` : room.mode === "preview" ? "Recovery options" : "Delay absorbed"}
      </h2>
      {impactCounts && phase === "impact" && (
        <p className="text-sm text-muted">
          {impactCounts.breach + impactCounts.blocked > 0 ? "The deadline breaks. " : "The deadline still holds, but slack is shrinking. "}
          {impactCounts.delayed} tasks slip{impactCounts.atRisk ? `, ${impactCounts.atRisk} more sit downstream at risk` : ""}.
        </p>
      )}

      {!runnable && run.options.length > 0 && run.status !== "running" && !showForm && (
        <button type="button" onClick={() => setShowForm(true)} className="text-xs text-muted underline underline-offset-2 hover:text-porcelain">
          Change priorities and run again
        </button>
      )}

      {(runnable || (showForm && run.status !== "running")) && (
        <div className="space-y-2 rounded-xl border border-line bg-panel p-3">
          <label htmlFor="priorities" className="block text-sm font-semibold">
            What matters most today?
          </label>
          <textarea
            id="priorities"
            value={priorities}
            onChange={(e) => setPriorities(e.target.value.slice(0, 500))}
            rows={2}
            placeholder="e.g. Sponsors need the vendor tables. Keep spend under €100."
            className="w-full resize-none rounded-md border border-line bg-raised px-2.5 py-2 text-sm placeholder:text-faint"
          />
          <div className="flex flex-wrap gap-1.5">
            {PRIORITY_CHIPS.map((chip) => (
              <button key={chip} type="button" onClick={() => setPriorities(chip)} className="rounded-full border border-line px-2.5 py-1 text-xs text-muted hover:border-focus hover:text-porcelain">
                {chip}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => {
              setShowForm(false);
              onRecover(priorities);
            }}
            className="w-full rounded-lg bg-focus px-3 py-2.5 text-sm font-bold text-graphite hover:brightness-110"
          >
            Find recovery options
          </button>
          <p className="text-[11px] leading-snug text-faint">
            {live
              ? "Runs NVIDIA Nemotron on Nebius Token Factory. The model proposes fixes; a constraint solver decides which ones actually work."
              : "This deployment runs a simulated agent: no model is called. Every option is still checked by the constraint solver."}
          </p>
          <button type="button" onClick={onSearch} disabled={state.pending === "search"} className="text-xs text-muted underline underline-offset-2 hover:text-porcelain disabled:opacity-50">
            {state.pending === "search" ? "Searching…" : "Or run the solver search without AI"}
          </button>
        </div>
      )}

      {run.status !== "idle" && run.source !== "search" && (
        <div className="rounded-xl border border-line bg-panel p-3" aria-live="polite">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold">
              {run.provider ? (run.provider.live ? `${modelName(run.provider.model)} on Nebius` : "Simulated agent") : "Starting…"}
            </h3>
            {run.status === "running" && (
              <button type="button" onClick={onCancel} className="text-xs text-muted underline underline-offset-2 hover:text-porcelain">
                Stop
              </button>
            )}
          </div>
          <ol className="mt-1 max-h-64 space-y-1 overflow-y-auto pr-1">
            {run.events.map((e) => (
              <TraceRow key={e.seq} event={e} />
            ))}
            {run.status === "running" && <li className="heartbeat text-xs text-focus">Waiting for the next step…</li>}
          </ol>
        </div>
      )}

      {run.status === "failed" && run.error && (
        <div role="alert" className="rounded-xl border border-coral/50 bg-panel p-3 text-sm">
          <p className="font-semibold text-coral">{run.error.code === "CANCELLED" ? "Run stopped." : "The recovery agent could not finish."}</p>
          <p className="mt-1 text-muted">{run.error.message}</p>
          <button type="button" onClick={onSearch} className="mt-2 rounded-md border border-line px-3 py-1.5 text-xs hover:border-porcelain">
            Run the solver search without AI
          </button>
        </div>
      )}

      {run.status === "done" && run.options.length === 0 && (
        <div role="status" className="rounded-xl border border-coral/50 bg-panel p-3 text-sm">
          <p className="font-semibold text-coral">No verified recovery found.</p>
          <p className="mt-1 text-muted">
            {run.summary ?? "No combination of permitted interventions keeps the deadline. The honest answer is to move doors or accept a late start."}
          </p>
        </div>
      )}

      {run.options.length > 0 && (
        <div>
          {run.source !== "search" && run.finalizedByModel === false && (
            <p className="mb-2 text-xs text-amber">The agent ran out of budget before choosing; showing its verified candidates.</p>
          )}
          {run.summary && <p className="mb-2 text-xs text-muted">{run.summary}</p>}
          <ul className="space-y-2">
            {run.options.map((o) => (
              <OptionCard
                key={o.id}
                option={o}
                selected={state.previewId === o.id}
                onPreview={() => onPreview(state.previewId === o.id ? null : o.id)}
                onApply={() => onApply(o)}
                applying={state.pending === "apply"}
                current={current}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
