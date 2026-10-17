"use client";

import Link from "next/link";
import { useCallback, useMemo } from "react";
import { shortId } from "@/lib/format";
import { useRoom } from "@/state/useRoom";
import { impactStory } from "@/lib/story";
import { IncidentDesk } from "./IncidentDesk";
import { HeaderMenu } from "./HeaderMenu";
import { Inspector } from "./LeftRail";
import { SceneHeader } from "./SceneHeader";
import { StartCard } from "./StartCard";
import { StepGuide } from "./StepGuide";
import { VenueScene } from "./VenueScene";
import { WhyItMatters } from "./WhyItMatters";
import { OperationsCanvas } from "./OperationsCanvas";
import { AiBadge, RecoveryPanel } from "./RecoveryPanel";
import { Timeline } from "./Timeline";

function downloadReport(payload: unknown, name: string) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json",
  });
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
  const resources = useMemo(
    () => new Map(scenario?.resources.map((r) => [r.id, r.label]) ?? []),
    [scenario],
  );
  const resourceLabel = useCallback(
    (id: string) => resources.get(id) ?? id,
    [resources],
  );

  if (!scenario || !room || !view) {
    return (
      <main className="grid min-h-dvh place-items-center p-6">
        {state.error ? (
          <div role="alert" className="max-w-md text-center">
            <p className="font-display text-3xl font-bold">
              The control room is offline
            </p>
            <p className="mt-2 text-muted">{state.error.message}</p>
            <button
              type="button"
              onClick={() => void actions.retryBoot()}
              className="mt-4 rounded-lg bg-focus px-4 py-2 font-bold text-graphite"
            >
              Try again
            </button>
          </div>
        ) : (
          <p className="heartbeat font-display text-2xl text-muted">
            Opening the control room…
          </p>
        )}
      </main>
    );
  }

  const impactCounts = view.impact
    ? {
        delayed:
          view.impact.metrics.delayed_count + view.impact.metrics.breach_count,
        atRisk: view.impact.metrics.at_risk_count,
        breach: view.impact.metrics.breach_count,
        blocked: view.impact.metrics.blocked_count,
      }
    : null;
  const busy = state.pending !== null || state.run.status === "running";
  const story = impactStory(scenario, view, room);
  const incidentDesk = (heading: string | null) => (
    <IncidentDesk
      key={state.history.length}
      heading={heading}
      presets={state.demo!.presets}
      disabled={busy}
      intake={state.intake}
      live={state.health?.ai.mode === "live"}
      onInterpret={(text) => void actions.interpret(text)}
      onConfirm={(result) =>
        void actions.confirmIntake(result, { ...result.preferences })
      }
      onDiscard={actions.clearIntake}
      onPreset={(id) => void actions.shock(id)}
    />
  );
  const date = new Date(`${scenario.date}T12:00:00`).toLocaleDateString(
    "en-GB",
    { day: "numeric", month: "long" },
  );

  const exportReport = () =>
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
        options: state.run.options.map((o) => ({
          id: o.id,
          title: o.title,
          source: o.source,
          status: o.evaluation.status,
          cost_cents: o.evaluation.cost_cents,
          readiness: o.evaluation.schedule?.readiness,
          patch: o.evaluation.patch,
        })),
      },
      `ripple-room-${shortId(view.revision.id)}.json`,
    );

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center gap-x-3 gap-y-2 border-b sm:gap-x-5 border-line px-4 py-2 sm:flex-wrap sm:py-2.5 lg:px-6">
        <h1 className="shrink-0">
          <Link
            href="/"
            className="font-display text-[15px] leading-[0.95] font-extrabold tracking-wide sm:text-2xl sm:leading-normal"
          >
            Ripple <br className="sm:hidden" />
            Room
          </Link>
        </h1>
        <p className="text-sm text-muted max-sm:hidden">
          <span className="font-semibold text-porcelain">{scenario.name}</span>{" "}
          at {scenario.venue}, {date}
        </p>
        <div className="ml-auto flex min-w-0 items-center justify-end gap-1.5 max-sm:flex-1 sm:flex-wrap sm:gap-2">
          <AiBadge health={state.health} />
          <span
            className="hidden rounded-md border border-line px-2 py-1 text-xs text-muted sm:inline"
            title={view.revision.id}
          >
            Revision {shortId(view.revision.id)} ({state.history.length})
          </span>
          <button
            type="button"
            onClick={actions.undo}
            disabled={state.history.length <= 1 || busy}
            className="min-h-10 shrink-0 rounded-md border border-line px-2 py-1 text-xs hover:border-porcelain disabled:opacity-40 sm:min-h-0 sm:px-2.5"
          >
            Undo
          </button>
          <button
            type="button"
            onClick={actions.reset}
            disabled={state.history.length <= 1}
            className="min-h-10 shrink-0 rounded-md border border-line px-2 py-1 text-xs hover:border-porcelain disabled:opacity-40 sm:min-h-0 sm:px-2.5"
          >
            Reset
          </button>
          <button
            type="button"
            onClick={exportReport}
            className="rounded-md border border-line px-2.5 py-1 text-xs hover:border-porcelain max-sm:hidden"
          >
            Export report
          </button>
          <HeaderMenu>
            {(close) => (
              <>
                <p className="text-muted">
                  <span className="font-semibold text-porcelain">{scenario.name}</span>{" "}
                  at {scenario.venue}, {date}
                </p>
                <p className="mt-1 text-xs text-muted">
                  Revision {shortId(view.revision.id)}, {state.history.length}{" "}
                  {state.history.length === 1 ? "version" : "versions"} kept for undo
                </p>
                <button
                  type="button"
                  onClick={() => {
                    exportReport();
                    close();
                  }}
                  className="mt-3 min-h-10 w-full rounded-md border border-line-strong px-3 py-2 text-left text-sm font-semibold hover:border-porcelain"
                >
                  Export report (JSON)
                </button>
              </>
            )}
          </HeaderMenu>
        </div>
      </header>

      {state.error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 border-b border-coral/40 bg-[#1d1216] px-4 py-2 text-sm lg:px-6"
        >
          <span>
            <span className="font-semibold text-coral">
              {state.error.code === "STALE_REVISION"
                ? "That option is out of date."
                : "Something went wrong."}
            </span>{" "}
            {state.error.message}
          </span>
          <button
            type="button"
            onClick={actions.dismissError}
            className="text-xs text-muted underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <StepGuide phase={phase} shocked={state.history.length > 1} />

      <main className="grid flex-1 grid-cols-1 content-start gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_360px] lg:px-6">
        <section
          aria-labelledby="scene-h"
          className="min-w-0 overflow-hidden rounded-2xl border border-line bg-panel lg:col-start-1 lg:row-start-1"
        >
          <SceneHeader
            room={room}
            story={story}
            beforeIncident={
              view.revision.state.plan.entries.find(
                (e) => e.task_id === scenario.deadline_task_id,
              )?.start ?? null
            }
            doNothing={view.impact?.schedule.readiness ?? null}
          />
          <div className="overflow-x-auto">
            <VenueScene
              scenario={scenario}
              room={room}
              rippleKey={state.rippleKey}
              previewKey={state.previewId ?? ""}
            />
          </div>
        </section>

        <aside
          className="min-w-0 space-y-4 lg:col-start-2 lg:row-span-4 lg:row-start-1"
          aria-label="Next action"
        >
          {phase === "ready" && state.history.length === 1 ? (
            <>
              <StartCard
                onTruck={() => void actions.shock("truck-delay-35")}
                disabled={busy}
              />
              {incidentDesk("Or try another incident")}
            </>
          ) : (
            <>
              <RecoveryPanel
                scenario={scenario}
                doNothingReadiness={view.impact?.schedule.readiness ?? null}
                onPreferences={actions.setPreferences}
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
              <details className="rounded-xl border border-line p-3">
                <summary className="cursor-pointer text-sm font-semibold">
                  Add another incident
                </summary>
                <div className="mt-3">{incidentDesk(null)}</div>
              </details>
            </>
          )}
        </aside>

        <section
          aria-labelledby="ripple-h"
          className="min-w-0 rounded-2xl border border-line bg-[#0c1219] lg:col-start-1"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2 px-4 pt-3">
            <h2 id="ripple-h" className="font-display text-xl font-bold">
              How it spreads
            </h2>
            <p className="text-xs text-faint">
              Each line is a dependency: a job waits for every job that feeds
              it.
            </p>
          </div>
          <div className="overflow-x-auto">
            <OperationsCanvas
              scenario={scenario}
              room={room}
              rippleKey={state.rippleKey}
              focusTaskId={state.focusTaskId}
              onFocus={actions.focus}
              resourceLabel={resourceLabel}
            />
          </div>
          <div className="px-3 pb-3">
            <Inspector
              room={room}
              taskId={state.focusTaskId}
              resourceLabel={resourceLabel}
            />
          </div>
        </section>

        {/* Scrolls sideways on phones and holds no controls, so it takes focus itself for arrow-key scrolling. */}
        <section
          aria-label="Timeline"
          tabIndex={0}
          className="min-w-0 overflow-x-auto rounded-2xl border border-line bg-panel p-2 lg:col-start-1"
        >
          <div className="flex items-center justify-between px-2 pb-1 text-xs text-faint">
            <span>
              {room.mode === "impact"
                ? "Dashed outlines: the plan before the incident"
                : room.mode === "preview"
                  ? `Previewing ${preview?.title ?? "option"}. Dashed outlines: if nobody acts`
                  : "Today's plan"}
            </span>
            <span>Bold rows set the doors time</span>
          </div>
          <Timeline
            scenario={scenario}
            room={room}
            focusTaskId={state.focusTaskId}
            onFocus={actions.focus}
          />
        </section>

        <div className="min-w-0 lg:col-start-1">
          <WhyItMatters />
        </div>
      </main>
      <footer className="px-4 pb-4 text-[11px] text-faint lg:px-6">
        {scenario.disclaimer}
      </footer>
    </div>
  );
}
