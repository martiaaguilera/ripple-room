"use client";

import type { ShockPreset } from "@/lib/api/types";
import { clock, delta } from "@/lib/format";
import { useTween } from "@/lib/useTween";
import { STATUS_TEXT, type RoomView } from "@/lib/viewmodel";

export function DoorsBoard({ room }: { room: RoomView }) {
  const shown = useTween(room.readiness);
  const late = room.deadlineDelta != null && room.deadlineDelta > 0;
  const margin = room.deadlineDelta == null ? null : -room.deadlineDelta;
  const label =
    room.readiness == null
      ? "Doors cannot open: a task is blocked."
      : late
        ? `${room.deadlineDelta} min late`
        : margin === 0
          ? "Exactly on time"
          : `${margin} min to spare`;
  const caption = room.mode === "impact" ? "If nobody acts" : room.mode === "preview" ? "With this option" : "Current plan";
  return (
    <section aria-labelledby="doors-h" className="rounded-xl border border-line bg-panel p-4" aria-live="polite">
      <h2 id="doors-h" className="text-sm text-muted">
        {caption}
      </h2>
      <div className="mt-2 grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-faint">Ready for doors</div>
          <div className={`font-display text-5xl leading-none font-bold ${late ? "text-coral" : "text-porcelain"}`}>
            {shown != null ? clock(shown) : "—"}
          </div>
        </div>
        <div>
          <div className="text-xs text-faint">Doors open</div>
          <div className="font-display text-5xl leading-none font-bold text-amber">{clock(room.deadline)}</div>
        </div>
      </div>
      <p className={`mt-3 text-sm font-semibold ${late ? "text-coral" : "text-signal"}`}>
        <span aria-hidden className="mr-1.5 inline-block">
          {late ? "▲" : "●"}
        </span>
        {label}
      </p>
    </section>
  );
}

export function ShockDeck({
  presets,
  disabled,
  pendingId,
  onShock,
}: {
  presets: ShockPreset[];
  disabled: boolean;
  pendingId: string | null;
  onShock: (id: string) => void;
}) {
  return (
    <section aria-labelledby="break-h">
      <h2 id="break-h" className="font-display text-2xl font-bold">
        Break the plan
      </h2>
      <p className="mt-1 text-sm text-muted">Pick an incident and watch it travel through the day.</p>
      <ul className="mt-3 grid gap-2">
        {presets.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onShock(p.id)}
              className="group w-full rounded-lg border border-line bg-raised px-3 py-2.5 text-left transition-colors hover:border-amber disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="block text-[15px] font-semibold group-hover:text-amber">
                {pendingId === p.id ? "Applying…" : p.title}
              </span>
              <span className="block text-xs text-muted">{p.subtitle}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Inspector({ room, taskId, resourceLabel }: { room: RoomView; taskId: string | null; resourceLabel: (id: string) => string }) {
  const task = taskId ? room.byId[taskId] : null;
  if (!task) {
    return (
      <section className="rounded-xl border border-dashed border-line p-4 text-sm text-muted">
        Point at any task to see what holds it in place.
      </section>
    );
  }
  const crew = Object.entries(task.assignments);
  return (
    <section aria-labelledby="insp-h" className="rounded-xl border border-line bg-panel p-4 text-sm" aria-live="polite">
      <h2 id="insp-h" className="text-base font-bold">
        {task.label}
      </h2>
      <p className="mt-0.5 text-muted">
        {task.start != null ? `${clock(task.start)}–${clock(task.end ?? task.start)}` : "Not scheduled"}
        {task.delay ? `, ${delta(task.delay)}` : ""}
        {`, ${STATUS_TEXT[task.status].toLowerCase()}`}
      </p>
      {task.binding && (
        <p className="mt-2">
          <span className="text-faint">Why not earlier: </span>
          {task.binding.text}
          {task.binding.constraint_id && <code className="ml-1.5 rounded bg-raised px-1.5 py-0.5 text-[11px] text-muted">{task.binding.constraint_id}</code>}
        </p>
      )}
      {task.slack != null && (
        <p className="mt-1">
          <span className="text-faint">Slack before doors: </span>
          <span className={task.slack < 0 ? "font-semibold text-coral" : ""}>{task.slack} min</span>
        </p>
      )}
      {crew.length > 0 && (
        <p className="mt-1">
          <span className="text-faint">Assigned: </span>
          {crew.map(([, rid]) => resourceLabel(rid)).join(", ")}
        </p>
      )}
      {task.change && (
        <p className="mt-2 rounded-md bg-raised px-2 py-1.5 text-focus">
          {task.change.deferred
            ? "Deferred until after doors open."
            : [
                task.change.moved_minutes ? `Moves ${delta(task.change.moved_minutes)}` : null,
                task.change.duration_to != null ? `shortened ${task.change.duration_from}→${task.change.duration_to} min` : null,
                ...task.change.reassigned.map(([, from, to]) => `${from ? resourceLabel(from) : "none"} → ${resourceLabel(to)}`),
              ]
                .filter(Boolean)
                .join("; ")}
        </p>
      )}
    </section>
  );
}
