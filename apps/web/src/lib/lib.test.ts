import { describe, expect, it } from "vitest";
import fixtures from "@/test/fixtures.json";
import { parseFrame } from "./api/sse";
import type { DemoPayload, RevisionView, SearchResponse } from "./api/types";
import { clock, delta, doorsGap, eur } from "./format";
import { layoutGraph } from "./layout";
import { buildRoomView, touchedTasks } from "./viewmodel";

const demo = fixtures.demo as unknown as DemoPayload;
const shocked = fixtures.shocked as unknown as RevisionView;
const search = fixtures.search as unknown as SearchResponse;

describe("format", () => {
  it("formats clock, deltas and money", () => {
    expect(clock(1080)).toBe("18:00");
    expect(clock(845)).toBe("14:05");
    expect(delta(15)).toBe("+15 min");
    expect(delta(-20)).toBe("−20 min");
    expect(delta(0)).toBe("on time");
    expect(eur(3500)).toBe("€35");
    expect(eur(12750)).toBe("€127.50");
    expect(eur(0)).toBe("€0");
  });

  it("states the doors verdict in words, not only colour", () => {
    expect(doorsGap(1095, 1080)).toEqual({ text: "15 min late", tone: "late" });
    expect(doorsGap(1060, 1080)).toEqual({ text: "20 min spare", tone: "spare" });
    expect(doorsGap(1080, 1080)).toEqual({ text: "on time", tone: "tight" });
    expect(doorsGap(null, 1080)).toEqual({ text: "blocked", tone: "blocked" });
  });
});

describe("layoutGraph", () => {
  const layout = layoutGraph(demo.scenario);

  it("places every task exactly once inside its zone column", () => {
    expect(Object.keys(layout.nodes).sort()).toEqual(demo.scenario.tasks.map((t) => t.id).sort());
    for (const task of demo.scenario.tasks) {
      const node = layout.nodes[task.id]!;
      const band = layout.zones.find((z) => z.id === task.zone_id)!;
      expect(node.x).toBeGreaterThanOrEqual(band.x);
      expect(node.x + node.w).toBeLessThanOrEqual(band.x + band.w + 8);
    }
  });

  it("never overlaps nodes in a column", () => {
    const byZone = new Map<string, { y: number; h: number }[]>();
    for (const n of Object.values(layout.nodes)) byZone.set(n.zoneId, [...(byZone.get(n.zoneId) ?? []), n]);
    for (const nodes of byZone.values()) {
      nodes.sort((a, b) => a.y - b.y);
      for (let i = 1; i < nodes.length; i++) expect(nodes[i]!.y).toBeGreaterThanOrEqual(nodes[i - 1]!.y + nodes[i - 1]!.h);
    }
  });

  it("draws one path per dependency and is deterministic", () => {
    expect(layout.edges).toHaveLength(demo.scenario.dependencies.length);
    expect(layoutGraph(demo.scenario)).toEqual(layout);
    for (const e of layout.edges) expect(e.length).toBeGreaterThan(0);
  });
});

describe("buildRoomView", () => {
  it("shows the verified baseline as a plan with slack", () => {
    const room = buildRoomView(demo.scenario, demo.initial, null);
    expect(room.mode).toBe("plan");
    expect(room.readiness).toBe(17 * 60 + 40);
    expect(room.deadlineDelta).toBeLessThan(0);
    expect(room.tasks.every((t) => t.status === "on_track")).toBe(true);
  });

  it("derives impact statuses, waves and ghosts from the server report", () => {
    const room = buildRoomView(demo.scenario, shocked, null);
    expect(room.mode).toBe("impact");
    expect(room.byId["doors-open"]!.status).toBe("breach");
    expect(room.byId["truck-arrival"]!.wave).toBe(0);
    expect(room.byId["scanner-setup"]!.status).toBe("on_track");
    expect(room.byId["stage-rigging"]!.ghost).not.toBeNull();
    expect(room.sources).toEqual(["truck-arrival"]);
  });

  it("previews a verified option against the do-nothing plan", () => {
    const option = search.options[0]!.evaluation;
    const room = buildRoomView(demo.scenario, shocked, option);
    expect(room.mode).toBe("preview");
    expect(room.deadlineDelta).toBeLessThanOrEqual(0);
    const rigging = room.byId["stage-rigging"]!;
    expect(rigging.shift).toBe(rigging.start! - rigging.ghost!.start);
    expect(touchedTasks(option, shocked).length).toBeGreaterThan(0);
  });
});

describe("parseFrame", () => {
  it("parses SSE frames and ignores comments", () => {
    const frame = 'event: phase\ndata: {"seq":3,"type":"phase","at_ms":12,"data":{"name":"verify"}}';
    expect(parseFrame(frame)).toEqual({ seq: 3, type: "phase", at_ms: 12, data: { name: "verify" } });
    expect(parseFrame(": keep-alive")).toBeNull();
  });

  it("rejects unknown event types", () => {
    expect(() => parseFrame('data: {"seq":1,"type":"exec","at_ms":0,"data":{}}')).toThrow();
  });
});
