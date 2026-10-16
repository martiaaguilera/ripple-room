import type { CausalEdge, Evaluation, RevisionView, Scenario, TaskChange, TaskStatus, TaskTiming } from "./api/types";

/**
 * One render model for canvas + timeline + inspector, derived only from server
 * truth (verified plan, impact report, or a verified evaluation preview).
 */

export type ViewMode = "plan" | "impact" | "preview";
export type DisplayStatus = TaskStatus | "deferred";

export interface TaskView {
  id: string;
  label: string;
  zoneId: string;
  milestone: boolean;
  start: number | null;
  end: number | null;
  status: DisplayStatus;
  delay: number | null;
  wave: number | null;
  assignments: Record<string, string>;
  binding: TaskTiming["binding"] | null;
  slack: number | null;
  ghost: { start: number; end: number } | null;
  change: TaskChange | null;
  /** Preview only: minutes earlier (<0) or later (>0) than if nobody acts. */
  shift: number | null;
  critical: boolean;
}

export interface RoomView {
  mode: ViewMode;
  tasks: TaskView[];
  byId: Record<string, TaskView>;
  readiness: number | null;
  deadline: number;
  deadlineDelta: number | null;
  drivingPath: string[];
  causalEdges: CausalEdge[];
  sources: string[];
}

function durationsFrom(timings: TaskTiming[]): Map<string, TaskTiming> {
  return new Map(timings.map((t) => [t.task_id, t]));
}

export function buildRoomView(scenario: Scenario, current: RevisionView, preview: Evaluation | null): RoomView {
  const refStarts = new Map(current.revision.state.plan.entries.map((e) => [e.task_id, e.start]));
  const durations = new Map(scenario.tasks.map((t) => [t.id, t.duration]));

  let mode: ViewMode;
  let timings: TaskTiming[];
  let schedule;
  let statuses = new Map<string, { status: TaskStatus; delay: number | null; wave: number | null }>();
  let ghosts = new Map<string, { start: number; end: number }>();
  let causalEdges: CausalEdge[] = [];
  let sources: string[] = [];
  const changes = new Map<string, TaskChange>();
  const deferred = new Set<string>();

  if (preview && preview.schedule) {
    mode = "preview";
    timings = preview.timings;
    schedule = preview.schedule;
    for (const c of preview.changes) {
      changes.set(c.task_id, c);
      if (c.deferred) deferred.add(c.task_id);
    }
    // Ghost = what happens if nobody acts (impact) when available, else the reference plan.
    const before = current.impact ? durationsFrom(current.impact.timings) : null;
    for (const t of timings) {
      const b = before?.get(t.task_id);
      if (b) ghosts.set(t.task_id, { start: b.start, end: b.end });
    }
  } else if (current.impact) {
    mode = "impact";
    timings = current.impact.timings;
    schedule = current.impact.schedule;
    statuses = new Map(current.impact.tasks.map((t) => [t.task_id, { status: t.status, delay: t.delay ?? null, wave: t.wave ?? null }]));
    causalEdges = current.impact.causal_edges;
    sources = current.impact.sources;
    ghosts = new Map(
      [...refStarts].map(([id, start]) => [id, { start, end: start + (durations.get(id) ?? 0) }]),
    );
  } else if (current.plan_view) {
    mode = "plan";
    timings = current.plan_view.timings;
    schedule = current.plan_view.schedule;
  } else {
    throw new Error("Revision view has neither a verified plan nor an impact report.");
  }

  const timingById = durationsFrom(timings);
  const driving = new Set(schedule.driving_path);
  const tasks: TaskView[] = scenario.tasks.map((task) => {
    const t = timingById.get(task.id);
    const s = statuses.get(task.id);
    const isDeferred = deferred.has(task.id);
    let status: DisplayStatus = s?.status ?? "on_track";
    if (isDeferred) status = "deferred";
    if (mode === "impact" && !t && !s) status = "blocked";
    return {
      id: task.id,
      label: task.label,
      zoneId: task.zone_id,
      milestone: Boolean(task.milestone),
      start: t?.start ?? null,
      end: t?.end ?? null,
      status,
      delay: s?.delay ?? null,
      wave: s?.wave ?? null,
      assignments: t?.assignments ?? {},
      binding: t?.binding ?? null,
      slack: t?.slack ?? null,
      ghost: ghosts.get(task.id) ?? null,
      change: changes.get(task.id) ?? null,
      shift: mode === "preview" && t && ghosts.get(task.id) ? t.start - ghosts.get(task.id)!.start : null,
      critical: driving.has(task.id),
    };
  });

  return {
    mode,
    tasks,
    byId: Object.fromEntries(tasks.map((t) => [t.id, t])),
    readiness: schedule.readiness ?? null,
    deadline: schedule.deadline,
    deadlineDelta: schedule.deadline_delta ?? null,
    drivingPath: schedule.driving_path,
    causalEdges,
    sources,
  };
}

export const STATUS_TEXT: Record<DisplayStatus, string> = {
  on_track: "On track",
  at_risk: "At risk",
  delayed: "Delayed",
  breach: "Misses deadline",
  blocked: "Blocked",
  deferred: "Deferred",
};

/**
 * Tasks an option actually touches compared with doing nothing: moved, reassigned,
 * shortened or deferred. Forced shifts caused by the incident itself are excluded.
 */
export function touchedTasks(option: Evaluation, current: RevisionView): string[] {
  const before = new Map((current.impact?.timings ?? []).map((t) => [t.task_id, t]));
  const out = new Set<string>();
  for (const c of option.changes) {
    if (c.deferred || c.duration_to != null || c.reassigned.length) out.add(c.task_id);
  }
  for (const t of option.timings) {
    const b = before.get(t.task_id);
    if (b && b.start !== t.start) out.add(t.task_id);
  }
  return [...out];
}
