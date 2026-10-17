"use client";

import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "@/lib/useReducedMotion";
import type { AgentEvent } from "@/lib/api/sse";
import type { Health, Preferences, Scenario } from "@/lib/api/types";
import { clock, delta, eur } from "@/lib/format";
import type { RoomView } from "@/lib/viewmodel";
import type { Phase, RecoveryOption, RoomState } from "@/state/room";
import { NoticeCard } from "./NoticeCard";
import { PreferencesPanel } from "./PreferencesPanel";
import { VerifierBoard } from "./VerifierBoard";

const PHASE_TEXT: Record<string, string> = {
  perceive: "Reading the situation",
  diagnose: "Diagnosing the delay",
  plan: "Weighing permitted fixes",
  verify: "Verifying a proposal",
  revise: "Revising after verifier feedback",
  present: "Presenting options",
};

const SOURCE_TEXT: Record<RecoveryOption["source"], string> = {
  nemotron: "Proposed by Nemotron",
  mock: "Simulated agent",
  search: "Playbook search, no AI",
};

const DIMENSION_SHADE: Record<string, string> = {
  guest: "var(--coral)",
  spend: "var(--amber)",
  crew: "var(--focus)",
  margin: "var(--muted)",
};

export function modelName(id: string): string {
  const m = id.split("/").pop() ?? id;
  if (/super/i.test(m)) return "Nemotron 3 Super";
  if (/ultra/i.test(m)) return "Nemotron 3 Ultra";
  if (/lightning/i.test(m)) return "Nemotron 3.5 Lightning";
  if (/nano/i.test(m)) return "Nemotron 3 Nano";
  return m;
}

export function AiBadge({ health }: { health: Health | null }) {
  if (!health)
    return <span className="text-xs text-faint">AI status unknown</span>;
  if (health.ai.status === "paused" || health.ai.status === "budget_exhausted")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/50 px-2.5 py-1 text-xs text-amber">
        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-amber" />
        {health.ai.status === "paused"
          ? "Live AI paused"
          : "Today's live AI budget used"}
      </span>
    );
  const live = health.ai.mode === "live";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${live ? "border-focus/50 text-focus" : "border-line text-muted"}`}
    >
      <span
        aria-hidden
        className={`h-1.5 w-1.5 rounded-full ${live ? "heartbeat bg-focus" : "bg-faint"}`}
      />
      {live
        ? `${modelName(health.ai.planner_model)} on Nebius Token Factory`
        : "Simulated agent, no model calls"}
    </span>
  );
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
          <code className="text-porcelain">{String(d.name)}</code>{" "}
          {String(d.summary)}
        </li>
      );
    case "error":
      return (
        <li className="text-xs font-semibold text-coral">
          {String(d.message)}
        </li>
      );
    case "done":
      return (
        <li className="pt-1 text-xs text-faint">
          Finished in {((Number(d.elapsed_ms) || 0) / 1000).toFixed(1)}s:{" "}
          {String(d.model_calls)} model calls, {String(d.evaluations)} verifier
          checks.
        </li>
      );
    default:
      return null;
  }
}

function PenaltyBar({ option }: { option: RecoveryOption }) {
  const lines = option.report.penalties.filter((p) => p.points > 0);
  const total = option.report.total_points;
  if (total <= 0)
    return (
      <p className="text-[11px] text-faint">
        0 penalty points under your priorities.
      </p>
    );
  return (
    <div>
      <div
        className="flex h-1.5 overflow-hidden rounded-full bg-raised"
        aria-hidden
      >
        {lines.map((p) => (
          <span
            key={p.dimension}
            style={{
              width: `${(p.points / total) * 100}%`,
              background: DIMENSION_SHADE[p.dimension],
            }}
          />
        ))}
      </div>
      <p className="mt-1 text-[11px] text-faint">
        {Math.round(total)} penalty points:{" "}
        {lines.map((p) => `${p.dimension} ${Math.round(p.points)}`).join(", ")}
      </p>
    </div>
  );
}

function OptionCard({
  option,
  selected,
  onPreview,
  onApply,
  applying,
}: {
  option: RecoveryOption;
  selected: boolean;
  onPreview: () => void;
  onApply: () => void;
  applying: boolean;
}) {
  const ev = option.evaluation;
  const ready = ev.schedule?.readiness;
  const spare =
    ev.schedule?.deadline_delta != null ? -ev.schedule.deadline_delta : null;
  const impacts = ev.service_impacts.map((s) => s.text);
  const breaches = option.report.breaches;
  return (
    <li>
      <article
        className={`rounded-xl border p-3 transition-colors ${selected ? "border-focus bg-[#121b2a]" : "border-line bg-panel hover:border-line-strong"}`}
      >
        <button
          type="button"
          onClick={onPreview}
          aria-pressed={selected}
          className="w-full text-left"
        >
          <div className="flex items-start gap-2">
            <span
              className={`mt-0.5 grid h-6 min-w-6 place-items-center rounded-md px-1 text-xs font-bold ${option.rank === 1 ? "bg-signal text-[var(--signal-ink)]" : "bg-raised text-muted"}`}
              title="Rank under your priorities"
            >
              {option.rank}
            </span>
            <div className="min-w-0 flex-1">
              <h3 className="text-[15px] leading-snug font-bold">
                {option.title}
              </h3>
              <p className="text-[11px] text-faint">
                {option.origin === "playbook"
                  ? "Standard fix from the playbook search, verified"
                  : option.origin === "no_change"
                    ? "No change needed, verified"
                    : option.modelRank == null
                      ? SOURCE_TEXT[option.source]
                      : option.source === "nemotron"
                        ? option.modelRank === 1
                          ? "Nemotron's own first choice"
                          : `Nemotron listed it #${option.modelRank}`
                        : `Simulated agent listed it #${option.modelRank}`}
              </p>
            </div>
            <span className="shrink-0 rounded border border-signal/50 bg-[#0d2422] px-1.5 py-px text-[11px] font-bold text-signal">
              <span aria-hidden>✓ </span>Verified
            </span>
          </div>
          <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
            <div>
              <dt className="text-muted">Ready</dt>
              <dd className="font-display text-xl font-bold">
                {ready != null ? clock(ready) : "—"}
              </dd>
              <dd className="text-muted">
                {spare != null
                  ? spare === 0
                    ? "no margin"
                    : `${spare} min spare`
                  : ""}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Extra cost</dt>
              <dd className="font-display text-xl font-bold">
                {eur(ev.cost_cents)}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Tasks touched</dt>
              <dd className="font-display text-xl font-bold">
                {option.touched.length}
              </dd>
            </div>
          </dl>
          <ul className="mt-2 space-y-0.5 text-xs">
            <li className={impacts.length ? "text-amber" : "text-muted"}>
              <span aria-hidden className="mr-1">
                {impacts.length ? "▲" : "–"}
              </span>
              {impacts.length
                ? `Guest-facing trade-off: ${impacts.join("; ")}`
                : "No guest-facing trade-off."}
            </li>
            {breaches.length > 0 ? (
              breaches.map((b) => (
                <li key={b.text} className="text-amber">
                  <span aria-hidden className="mr-1">
                    ▲
                  </span>
                  {b.text}
                </li>
              ))
            ) : (
              <li className="text-signal">
                <span aria-hidden className="mr-1">
                  ✓
                </span>
                Fits every priority you set.
              </li>
            )}
          </ul>
          {selected ? (
            <>
              <div className="mt-3">
                <PenaltyBar option={option} />
              </div>
              {option.why && option.origin === "model" && (
                <p className="mt-2 border-l-2 border-focus/50 pl-2 text-xs text-muted">
                  <span className="text-focus">
                    {option.source === "nemotron"
                      ? "Nemotron: "
                      : "Agent note: "}
                  </span>
                  {option.why}
                </p>
              )}
              <p className="mt-2 text-[11px] text-faint">
                Checked by CP-SAT (
                {ev.solver.status === "OPTIMAL"
                  ? "least disruptive timing for this fix, proven"
                  : "feasible, not proven least disruptive"}
                , {ev.solver.wall_ms} ms).
              </p>
            </>
          ) : (
            <p className="mt-2 text-xs font-semibold text-focus">
              Preview on the plan
            </p>
          )}
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
  scenario: Scenario;
  phase: Phase;
  state: RoomState;
  room: RoomView;
  doNothingReadiness: number | null;
  impactCounts: {
    delayed: number;
    atRisk: number;
    breach: number;
    blocked: number;
  } | null;
  onRecover: (priorities: string) => void;
  onCancel: () => void;
  onSearch: () => void;
  onPreview: (id: string | null) => void;
  onApply: (option: RecoveryOption) => void;
  onUndo: () => void;
  onPreferences: (p: Preferences) => void;
}

export function RecoveryPanel(props: PanelProps) {
  const {
    scenario,
    phase,
    state,
    room,
    doNothingReadiness,
    impactCounts,
    onRecover,
    onCancel,
    onSearch,
    onPreview,
    onApply,
    onUndo,
    onPreferences,
  } = props;
  const [words, setWords] = useState("");
  const [showForm, setShowForm] = useState(false);
  const appliedRef = useRef<HTMLHeadingElement>(null);
  const reduced = useReducedMotion();
  // The Apply button usually sits far down the page (always on phones): bring the
  // confirmation into view and move focus to it so the outcome is never off-screen.
  useEffect(() => {
    if (phase !== "applied") return;
    appliedRef.current?.focus({ preventScroll: true });
    appliedRef.current?.scrollIntoView({
      behavior: reduced ? "auto" : "smooth",
      block: "start",
    });
  }, [phase, reduced]);
  const run = state.run;
  const live = state.health?.ai.mode === "live";
  const aiBlocked =
    state.health?.ai.status === "paused" ||
    state.health?.ai.status === "budget_exhausted";
  const late = doNothingReadiness != null && doNothingReadiness > room.deadline;
  const hasOptions = run.options.length > 0;
  const showComposer =
    (phase === "impact" || phase === "options") &&
    run.status !== "running" &&
    (!hasOptions || showForm);

  if (phase === "ready" || phase === "applied") {
    return (
      <section aria-labelledby="rec-h" className="space-y-3">
        <h2
          id="rec-h"
          ref={appliedRef}
          tabIndex={-1}
          className="scroll-mt-4 font-display text-2xl font-bold"
        >
          {phase === "applied" ? "Recovery applied" : "The plan holds"}
        </h2>
        {phase === "applied" && (
          <div className="rounded-xl border border-signal/40 bg-panel p-3 text-sm">
            <p>
              <span className="font-semibold text-signal">
                {state.lastAppliedTitle ?? "Option"}
              </span>{" "}
              is now the working plan, re-verified by the server.
            </p>
            <button
              type="button"
              onClick={onUndo}
              className="mt-2 rounded-md border border-line px-3 py-1.5 text-xs hover:border-porcelain"
            >
              Undo
            </button>
          </div>
        )}
        {phase === "applied" && state.notice && (
          <NoticeCard notice={state.notice} />
        )}
        <div className="rounded-xl border border-line bg-panel p-3 text-sm">
          <h3 className="font-semibold">What sets the doors time</h3>
          <ol className="mt-2 space-y-1 text-muted">
            {room.drivingPath
              .filter(
                (id) => !room.byId[id]?.milestone || id === room.drivingPath[0],
              )
              .map((id) => (
                <li key={id} className="flex justify-between gap-2">
                  <span>{room.byId[id]?.label}</span>
                  <span className="text-faint">
                    {room.byId[id]?.start != null
                      ? clock(room.byId[id]!.start!)
                      : ""}
                  </span>
                </li>
              ))}
          </ol>
          <p className="mt-2 text-xs text-faint">
            Any delay on this chain moves the doors.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="rec-h" className="space-y-3">
      <h2 id="rec-h" className="font-display text-2xl font-bold">
        {late
          ? `Doors ${delta(doNothingReadiness! - room.deadline).replace("+", "")} late`
          : "Delay absorbed"}
      </h2>
      {impactCounts && (
        <p className="text-sm text-muted">
          {impactCounts.breach + impactCounts.blocked > 0
            ? "If nobody acts, the deadline breaks. "
            : "The deadline still holds, but slack is shrinking. "}
          {impactCounts.delayed} tasks slip
          {impactCounts.atRisk
            ? `, ${impactCounts.atRisk} more sit downstream at risk`
            : ""}
          .
        </p>
      )}

      {hasOptions && run.status !== "running" && !showForm && (
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="text-xs text-muted underline underline-offset-2 hover:text-porcelain"
        >
          Change priorities and run again
        </button>
      )}

      {showComposer && (
        <div className="space-y-3 rounded-xl border border-line bg-panel p-3">
          <h3 className="text-sm font-semibold">What matters most today?</h3>
          <PreferencesPanel
            scenario={scenario}
            value={state.preferences}
            onChange={onPreferences}
          />
          <div>
            <label htmlFor="words" className="text-xs text-muted">
              Anything else the planner should know? (optional)
            </label>
            <textarea
              id="words"
              value={words}
              onChange={(e) => setWords(e.target.value.slice(0, 500))}
              rows={2}
              placeholder="e.g. The lead is happy to lend a hand on stage."
              className="mt-1 w-full resize-none rounded-md border border-line bg-raised px-2.5 py-2 text-sm placeholder:text-faint"
            />
          </div>
          <button
            type="button"
            disabled={aiBlocked}
            onClick={() => {
              setShowForm(false);
              onRecover(words);
            }}
            className="w-full rounded-lg bg-focus px-3 py-2.5 text-sm font-bold text-graphite hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Find recovery options
          </button>
          {aiBlocked && (
            <p role="status" className="text-xs text-amber">
              {state.health?.ai.status === "paused"
                ? "Live AI is paused by the operator."
                : "Today's live AI budget is used up; it resets at midnight UTC."}{" "}
              The playbook search below still finds and verifies recoveries,
              without AI.
            </p>
          )}
          <p className="text-[11px] leading-snug text-faint">
            {live
              ? "NVIDIA Nemotron on Nebius Token Factory proposes fixes; a constraint solver decides which ones actually work; your priorities rank them."
              : "This deployment runs a simulated agent: no model is called. Every option is still checked by the constraint solver."}
          </p>
          <button
            type="button"
            onClick={onSearch}
            disabled={state.pending === "search"}
            className="text-xs text-muted underline underline-offset-2 hover:text-porcelain disabled:opacity-50"
          >
            {state.pending === "search"
              ? "Searching…"
              : "Or run the playbook search without AI"}
          </button>
        </div>
      )}

      {run.source !== "search" && run.status !== "idle" && (
        <VerifierBoard
          events={run.events}
          deadline={room.deadline}
          doNothing={doNothingReadiness}
        />
      )}

      {run.status !== "idle" && run.source !== "search" && (
        <details
          open={run.status === "running"}
          className="rounded-xl border border-line bg-panel p-3"
          aria-live="polite"
        >
          <summary className="cursor-pointer text-sm font-semibold">
            {run.provider
              ? run.provider.live
                ? `${modelName(run.provider.model)} on Nebius`
                : "Simulated agent"
              : run.status === "running"
                ? "Starting…"
                : "Agent did not start"}{" "}
            <span className="ml-1 text-xs font-normal text-muted">
              {run.status === "running"
                ? "working"
                : `${run.events.filter((e) => e.type === "tool_result").length} tool calls`}
            </span>
          </summary>
          {run.status === "running" && (
            <button
              type="button"
              onClick={onCancel}
              className="mt-1 text-xs text-muted underline underline-offset-2 hover:text-porcelain"
            >
              Stop
            </button>
          )}
          <ol className="mt-1 max-h-56 space-y-1 overflow-y-auto pr-1">
            {run.events.map((e) => (
              <TraceRow key={e.seq} event={e} />
            ))}
            {run.status === "running" && (
              <li className="heartbeat text-xs text-focus">
                Waiting for the next step…
              </li>
            )}
          </ol>
        </details>
      )}

      {run.status === "failed" && run.error && (
        <div
          role="alert"
          className="rounded-xl border border-coral/50 bg-panel p-3 text-sm"
        >
          <p className="font-semibold text-coral">
            {run.error.code === "CANCELLED"
              ? "Run stopped."
              : "The recovery agent could not finish."}
          </p>
          <p className="mt-1 text-muted">{run.error.message}</p>
          <button
            type="button"
            onClick={onSearch}
            className="mt-2 rounded-md border border-line px-3 py-1.5 text-xs hover:border-porcelain"
          >
            Run the playbook search without AI
          </button>
        </div>
      )}

      {run.status === "done" && !hasOptions && (
        <div
          role="status"
          className="rounded-xl border border-coral/50 bg-panel p-3 text-sm"
        >
          <p className="font-semibold text-coral">
            No verified recovery found.
          </p>
          <p className="mt-1 text-muted">
            {run.summary ??
              "No combination of permitted interventions keeps the deadline. The honest answer is to move doors or accept a late start."}
          </p>
        </div>
      )}

      {hasOptions && (
        <div>
          {run.source !== "search" && run.finalizedByModel === false && (
            <p className="mb-2 text-xs text-amber">
              The agent ran out of budget before choosing; showing its verified
              candidates.
            </p>
          )}
          {run.summary && (
            <p className="mb-2 text-xs text-muted">{run.summary}</p>
          )}
          <p className="mb-2 text-[11px] text-faint">
            Ranked by your priorities: fewest breaches first, then fewest
            penalty points.
          </p>
          <ul className="space-y-2">
            {run.options.map((o) => (
              <OptionCard
                key={o.id}
                option={o}
                selected={state.previewId === o.id}
                onPreview={() =>
                  onPreview(state.previewId === o.id ? null : o.id)
                }
                onApply={() => onApply(o)}
                applying={state.pending === "apply"}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
