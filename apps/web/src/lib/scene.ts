import type { Scenario } from "./api/types";
import { clock } from "./format";
import type { RoomView, TaskView } from "./viewmodel";

/**
 * Pure view helpers for the illustrative venue scene. Everything is derived from the plan's
 * scheduled times at a given scene minute; nothing here is telemetry or invented.
 */

const PERSON_KINDS = new Set(["person", "equipment"]);

export function initials(label: string): string {
  const words = label.replace(/technician/i, "tech").split(/\s+/);
  if (/^AV/i.test(label)) return label.toLowerCase().includes("backup") ? "AV2" : "AV";
  if (/trolley/i.test(label)) return label.toLowerCase().includes("rental") ? "T2" : "T1";
  return words
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

/** The stretch of the day the scene clock sweeps: a little before the first job to just past doors. */
export function sceneSpan(room: RoomView): { dayStart: number; dayEnd: number } {
  const starts = room.tasks.flatMap((t) => (t.start != null ? [t.start] : []));
  const ends = room.tasks.flatMap((t) => (t.end != null ? [t.end] : []));
  return {
    dayStart: Math.floor((Math.min(...starts) - 25) / 15) * 15,
    dayEnd: Math.max(room.deadline, ...ends) + 10,
  };
}

export interface TaskProgress {
  deferred: boolean;
  progress: number;
  done: boolean;
  active: boolean;
}

export function taskProgress(task: TaskView, minute: number): TaskProgress {
  const deferred = task.status === "deferred" || task.start == null || task.end == null;
  const start = task.start ?? 0;
  const end = task.end ?? 0;
  const progress = deferred ? 0 : Math.max(0, Math.min(1, (minute - start) / Math.max(1, end - start)));
  return { deferred, progress, done: progress >= 1, active: progress > 0 && progress < 1 };
}

/** True when the selected recovery moves, resizes or re-staffs this task. */
export function isChanged(task: TaskView): boolean {
  return Boolean(task.change && (task.shift || task.change.duration_to != null || task.change.reassigned.length));
}

export interface SceneToken {
  id: string;
  label: string;
  kind: string;
  initials: string;
  task: TaskView | undefined;
}

export interface SceneFrame {
  truck: { due: number | null; delay: number; late: boolean; approach: number; parked: boolean };
  dockOpen: boolean;
  doors: { deadline: number; ready: number | null; late: boolean; open: boolean };
  tokens: SceneToken[];
}

export function sceneFrame(scenario: Scenario, room: RoomView, minute: number, dayStart: number): SceneFrame {
  const truck = room.byId["truck-arrival"];
  const arrival = truck?.start ?? dayStart;
  const delay = truck?.delay ?? 0;
  // Waits at the road's far end, rolls in over the last 40 minutes, parks at the dock door.
  const approach = Math.max(0, Math.min(1, (minute - (arrival - 40)) / 40));

  const busy = new Map<string, TaskView>();
  for (const task of room.tasks) {
    if (task.start == null || task.end == null || task.end === task.start) continue;
    if (minute >= task.start && minute < task.end) for (const rid of Object.values(task.assignments)) busy.set(rid, task);
  }
  const used = new Set(room.tasks.flatMap((t) => Object.values(t.assignments)));
  const tokens = scenario.resources
    .filter((r) => PERSON_KINDS.has(r.kind) && (!r.standby || used.has(r.id)))
    .map((r) => ({ id: r.id, label: r.label, kind: r.kind, initials: initials(r.label), task: busy.get(r.id) }));

  const ready = room.readiness;
  const late = ready != null && ready > room.deadline;
  return {
    truck: { due: truck?.start ?? null, delay, late: delay > 0 && room.mode !== "plan", approach, parked: approach >= 1 },
    dockOpen: minute >= (room.byId["dock-open"]?.start ?? 0),
    doors: { deadline: room.deadline, ready, late, open: minute >= room.deadline && ready != null && ready <= room.deadline },
    tokens,
  };
}

export type RoomTagTone = "late" | "breach" | "changed" | null;

export interface RoomLine {
  text: string;
  tag: string | null;
  tone: RoomTagTone;
}

/** One sentence per room for the phone scene: what is happening there now, or next, or that it is done. */
export function roomLine(tasks: TaskView[], minute: number, mode: RoomView["mode"]): RoomLine {
  const live = tasks.filter((t) => !taskProgress(t, minute).deferred);
  // Same window as crew placement: a job is under way from its start minute until its end.
  const active = live.filter((t) => (t.start ?? 0) <= minute && minute < (t.end ?? 0));
  const upcoming = live.filter((t) => (t.start ?? 0) > minute).sort((a, b) => (a.start ?? 0) - (b.start ?? 0));
  const deferred = tasks.length - live.length;

  const now = active[0];
  const next = upcoming[0];
  const only = live[0];
  const focus = now ?? next;
  let text: string;
  if (now) {
    text = `Now: ${now.label}, until ${clock(now.end ?? 0)}${active.length > 1 ? ` (+${active.length - 1} more)` : ""}`;
  } else if (next) {
    text = `Next: ${next.label} at ${clock(next.start ?? 0)}`;
  } else if (only) {
    text = live.length === 1 ? `${only.label} done` : `All ${live.length} jobs done`;
  } else {
    text = "Nothing scheduled";
  }
  if (deferred && !active.length && !upcoming.length) text += `, ${deferred} moved later`;

  if (focus && mode === "impact" && focus.delay != null && focus.delay > 0) {
    const breach = focus.status === "breach" || focus.status === "blocked";
    return { text, tag: `+${focus.delay} min`, tone: breach ? "breach" : "late" };
  }
  if (focus && mode === "preview" && isChanged(focus)) return { text, tag: "changed", tone: "changed" };
  return { text, tag: null, tone: null };
}
