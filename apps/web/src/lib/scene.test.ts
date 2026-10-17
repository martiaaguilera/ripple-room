import { describe, expect, it } from "vitest";
import fixtures from "@/test/fixtures.json";
import type { AgentEvent } from "./api/sse";
import type { DemoPayload, RevisionView } from "./api/types";
import { runProgress } from "./run";
import { initials, roomLine, sceneFrame, sceneSpan, taskProgress } from "./scene";
import { buildRoomView } from "./viewmodel";

const demo = fixtures.demo as unknown as DemoPayload;
const shocked = fixtures.shocked as unknown as RevisionView;

describe("venue scene helpers", () => {
  const plan = buildRoomView(demo.scenario, demo.initial, null);
  const impact = buildRoomView(demo.scenario, shocked, null);

  it("sweeps from before the first job to past the doors", () => {
    const { dayStart, dayEnd } = sceneSpan(plan);
    expect(dayStart % 15).toBe(0);
    expect(dayStart).toBeLessThan(Math.min(...plan.tasks.flatMap((t) => (t.start != null ? [t.start] : []))));
    expect(dayEnd).toBeGreaterThan(plan.deadline);
  });

  it("derives task progress from scheduled times only", () => {
    const task = plan.tasks.find((t) => !t.milestone && t.start != null && t.end != null && t.end > t.start)!;
    expect(taskProgress(task, task.start! - 1)).toMatchObject({ progress: 0, active: false, done: false });
    expect(taskProgress(task, task.end!)).toMatchObject({ progress: 1, done: true, active: false });
    const mid = Math.floor((task.start! + task.end!) / 2);
    expect(taskProgress(task, mid).active).toBe(true);
  });

  it("puts crew in the room of the job they are doing, otherwise free", () => {
    const { dayStart } = sceneSpan(plan);
    const early = sceneFrame(demo.scenario, plan, dayStart, dayStart);
    expect(early.tokens.length).toBeGreaterThan(0);
    expect(early.tokens.every((t) => t.task === undefined)).toBe(true);
    const busyTask = plan.tasks.find((t) => Object.keys(t.assignments).length && t.start != null && t.end! > t.start)!;
    const during = sceneFrame(demo.scenario, plan, busyTask.start!, dayStart);
    const assigned = new Set(Object.values(busyTask.assignments));
    expect(during.tokens.some((t) => assigned.has(t.id) && t.task?.id === busyTask.id)).toBe(true);
  });

  it("opens the doors only at the deadline and only when the plan is ready", () => {
    const { dayStart } = sceneSpan(plan);
    expect(sceneFrame(demo.scenario, plan, plan.deadline - 1, dayStart).doors.open).toBe(false);
    expect(sceneFrame(demo.scenario, plan, plan.deadline, dayStart).doors.open).toBe(true);
    const late = sceneFrame(demo.scenario, impact, impact.deadline + 5, dayStart);
    expect(late.doors.late).toBe(true);
    expect(late.doors.open).toBe(false);
    expect(late.truck.late).toBe(true);
    expect(late.truck.delay).toBe(35);
  });

  it("states each room's activity in words, with the delay as a tag", () => {
    const dock = demo.scenario.zones.slice().sort((a, b) => a.order - b.order)[0]!;
    const tasks = impact.tasks.filter((t) => t.zoneId === dock.id && !t.milestone);
    const first = tasks.slice().sort((a, b) => (a.start ?? 0) - (b.start ?? 0))[0]!;
    const before = roomLine(tasks, first.start! - 1, "impact");
    expect(before.text).toMatch(/^Next: /);
    expect(before.tag).toBe("+35 min");
    expect(roomLine(tasks, first.start!, "impact").text).toMatch(/^Now: /);
    expect(roomLine(tasks, 24 * 60, "plan")).toEqual({ text: `All ${tasks.length} jobs done`, tag: null, tone: null });
  });

  it("abbreviates crew labels for tokens", () => {
    expect(initials("Stage technician")).toBe("ST");
    expect(initials("AV technician")).toBe("AV");
    expect(initials("Backup AV technician")).toBe("BA");
  });
});

describe("agent run progress", () => {
  const ev = (seq: number, type: AgentEvent["type"], data: Record<string, unknown>): AgentEvent => ({ seq, type, at_ms: seq * 10, data });

  it("counts only what the server streamed", () => {
    const p = runProgress([
      ev(1, "run_started", {}),
      ev(2, "model_call", { n: 1 }),
      ev(3, "phase", { name: "perceive" }),
      ev(4, "tool_result", { name: "get_situation", ok: true, summary: "doors ready 18:15" }),
      ev(5, "phase", { name: "verify" }),
      ev(6, "candidate", { candidate_id: "c1", evaluation: { status: "infeasible" } }),
      ev(7, "candidate", { candidate_id: "c2", evaluation: { status: "verified" } }),
    ]);
    expect(p.current).toBe("verify");
    expect([...p.visited]).toEqual(["perceive", "verify"]);
    expect(p.steps).toBe(1);
    expect(p.checked).toBe(2);
    expect(p.holds).toBe(1);
    expect(p.latest).toEqual({ name: "get_situation", summary: "doors ready 18:15", ok: true });
  });

  it("starts empty before the first phase", () => {
    expect(runProgress([])).toMatchObject({ current: null, steps: 0, checked: 0, holds: 0, latest: null });
  });
});
