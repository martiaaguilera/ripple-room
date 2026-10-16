import type { RevisionView, Scenario, Shock } from "./api/types";
import { clock } from "./format";
import type { RoomView } from "./viewmodel";

/** Plain-language narration generated only from server data (shocks, impact, schedule). */

function list(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function describeShock(scenario: Scenario, shock: Shock): string {
  if (shock.kind === "task_delay") {
    const task = scenario.tasks.find((t) => t.id === shock.task_id);
    if (!task) return "An incident";
    const subject = task.id === "truck-arrival" ? "The truck arrives" : task.id === "dock-open" ? "The dock opens" : `${task.label} starts`;
    return `${subject} at ${clock(task.release + shock.delay_minutes)} instead of ${clock(task.release)}`;
  }
  const res = scenario.resources.find((r) => r.id === shock.resource_id);
  return `${res?.label ?? "A crew member"} is away ${clock(shock.window.start)}–${clock(shock.window.end)}`;
}

export interface Story {
  cause: string | null;
  chain: string | null;
  outcome: string;
  late: boolean;
}

export function impactStory(scenario: Scenario, view: RevisionView, room: RoomView): Story {
  const shocks = view.revision.state.shocks;
  const cause = shocks.length ? shocks.map((s) => describeShock(scenario, s as Shock)).join(". ") + "." : null;
  const pushed = room.drivingPath
    .map((id) => room.byId[id])
    .filter((t) => t && !t.milestone && (t.delay ?? 0) > 0)
    .map((t) => t!.label.toLowerCase());
  const blocked = room.tasks.filter((t) => t.status === "blocked" && !t.milestone).map((t) => t.label.toLowerCase());
  const chain = blocked.length
    ? `${list(blocked)} cannot happen at all as planned.`
    : pushed.length
      ? `That pushes ${list(pushed)} later.`
      : room.mode === "impact"
        ? "The jobs that set the doors time are not affected."
        : null;
  const late = room.readiness != null && room.readiness > room.deadline;
  let outcome: string;
  if (room.readiness == null) outcome = "Doors cannot open until the blocked work is solved.";
  else if (late) outcome = `Doors would be ready at ${clock(room.readiness)}, ${room.readiness - room.deadline} minutes after the ${clock(room.deadline)} opening.`;
  else {
    const spare = room.deadline - room.readiness;
    outcome = `Doors are ready at ${clock(room.readiness)}, ${spare === 0 ? "exactly on time" : `${spare} minutes to spare`}.`;
  }
  return { cause, chain, outcome, late };
}
