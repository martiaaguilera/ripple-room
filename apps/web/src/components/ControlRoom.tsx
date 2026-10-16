"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";
import { shortId } from "@/lib/format";
import { useRoom } from "@/state/useRoom";
import { DoorsBoard, Inspector, ShockDeck } from "./LeftRail";
import { OperationsCanvas } from "./OperationsCanvas";
import { AiBadge, RecoveryPanel } from "./RecoveryPanel";
import { Timeline } from "./Timeline";

function downloadReport(payload: unknown, name: string) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export function ControlRoom() {
  const { state, view, phase, room, preview, actions } = useRoom();
  const scenario = state.demo?.scenario;
  const resources = useMemo(() => new Map(scenario?.resources.map((r) => [r.id, r.label]) ?? []), [scenario]);
  const resourceLabel = useCallback((id: string) => resources.get(id) ?? id, [resources]);

  if (!scenario || !room || !view) {
    return (
      <main className="grid min-h-dvh place-items-center p-6">
        {state.error ? (
          <div role="alert" className="max-w-md text-center">
            <p className="font-display text-3xl font-bold">The control room is offline</p>
            <p className="mt-2 text-muted">{state.error.message}</p>
            <button type="button" onClick={() => void actions.retryBoot()} className="mt-4 rounded-lg bg-focus px-4 py-2 font-bold text-graphite">
              Try again
            </button>
          </div>
        ) : (
          <p className="heartbeat font-display text-2xl text-muted">Opening the control room…</p>
        )}
      </main>
    );
  }

  const impactCounts = view.impact
    ? {
        delayed: view.impact.metrics.delayed_count + view.impact.metrics.breach_count,
        atRisk: view.impact.metrics.at_risk_count,
        breach: view.impact.metrics.breach_count,
        blocked: view.impact.metrics.blocked_count,
      }
    : null;
  const busy = state.pending !== null || state.run.status === "running";
  const date = new Date(`${scenario.date}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long" });

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-line px-4 py-2.5 lg:px-6">
        <Link href="/" className="font-display text-2xl font-extrabold tracking-wide">
          Ripple Room
        </Link>
        <p className="text-sm text-muted">
          <span className="font-semibold text-porcelain">{scenario.name}</span> at {scenario.venue}, {date}
        </p>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <AiBadge health={state.health} />
          <span className="rounded-md border border-line px-2 py-1 text-xs text-muted" title={view.revision.id}>
            Revision {shortId(view.revision.id)} ({state.history.length})
          </span>
          <button type="button" onClick={actions.undo} disabled={state.history.length <= 1 || busy} className="rounded-md border border-line px-2.5 py-1 text-xs hover:border-porcelain disabled:opacity-40">
            Undo
          </button>
          <button type="button" onClick={actions.reset} disabled={state.history.length <= 1} className="rounded-md border border-line px-2.5 py-1 text-xs hover:border-porcelain disabled:opacity-40">
            Reset
          </button>
          <button
            type="button"
            onClick={() =>
              downloadReport(
                {
                  generated_at: new Date().toISOString(),
                  disclaimer: scenario.disclaimer,
                  revision: view.revision,
                  verified: view.verified,
                  readiness: room.readiness,
                  deadline: room.deadline,
                  impact_metrics: view.impact?.metrics ?? null,
                  agent_trace: state.run.events,
                  options: state.run.options.map((o) => ({ id: o.id, title: o.title, source: o.source, status: o.evaluation.status, cost_cents: o.evaluation.cost_cents, readiness: o.evaluation.schedule?.readiness, patch: o.evaluation.patch })),
                },
                `ripple-room-${shortId(view.revision.id)}.json`,
              )
            }
            className="rounded-md border border-line px-2.5 py-1 text-xs hover:border-porcelain"
          >
            Export report
          </button>
        </div>
      </header>

      {state.error && (
        <div role="alert" className="flex items-center justify-between gap-3 border-b border-coral/40 bg-[#1d1216] px-4 py-2 text-sm lg:px-6">
          <span>
            <span className="font-semibold text-coral">{state.error.code === "STALE_REVISION" ? "That option is out of date." : "Something went wrong."}</span> {state.error.message}
          </span>
          <button type="button" onClick={actions.dismissError} className="text-xs text-muted underline">
            Dismiss
          </button>
        </div>
      )}

      <div className="grid flex-1 grid-cols-1 gap-4 p-4 lg:grid-cols-[260px_minmax(0,1fr)_340px] lg:px-6">
        <aside className="order-1 space-y-4 lg:order-1">
          <DoorsBoard room={room} />
          <ShockDeck presets={state.demo!.presets} disabled={busy} pendingId={null} onShock={(id) => void actions.shock(id)} />
          <div className="hidden lg:block">
            <Inspector room={room} taskId={state.focusTaskId} resourceLabel={resourceLabel} />
          </div>
        </aside>

        <main className="order-3 min-w-0 space-y-4 lg:order-2">
          <section aria-label="Operations graph" className="overflow-x-auto rounded-xl border border-line bg-[#0c1219]">
            <OperationsCanvas scenario={scenario} room={room} rippleKey={state.rippleKey} focusTaskId={state.focusTaskId} onFocus={actions.focus} resourceLabel={resourceLabel} />
          </section>
          <div className="lg:hidden">
            <Inspector room={room} taskId={state.focusTaskId} resourceLabel={resourceLabel} />
          </div>
          <section aria-label="Timeline" className="overflow-x-auto rounded-xl border border-line bg-panel p-2">
            <div className="flex items-center justify-between px-2 pb-1 text-xs text-faint">
              <span>{room.mode === "impact" ? "Dashed outlines: the plan before the incident" : room.mode === "preview" ? `Previewing ${preview?.title ?? "option"}. Dashed outlines: if nobody acts` : "Today's plan"}</span>
              <span>Bold rows set the doors time</span>
            </div>
            <Timeline scenario={scenario} room={room} focusTaskId={state.focusTaskId} onFocus={actions.focus} />
          </section>
        </main>

        <aside className="order-2 lg:order-3">
          <RecoveryPanel
            current={view}
            phase={phase}
            state={state}
            room={room}
            impactCounts={impactCounts}
            onRecover={(p) => void actions.recover(p)}
            onCancel={actions.cancelRun}
            onSearch={() => void actions.search()}
            onPreview={actions.preview}
            onApply={(o) => void actions.apply(o)}
            onUndo={actions.undo}
          />
        </aside>
      </div>
      <footer className="px-4 pb-4 text-[11px] text-faint lg:px-6">{scenario.disclaimer}</footer>
    </div>
  );
}
