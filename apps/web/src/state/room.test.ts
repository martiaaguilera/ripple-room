import { describe, expect, it } from "vitest";
import fixtures from "@/test/fixtures.json";
import type { AgentEvent } from "@/lib/api/sse";
import type { DemoPayload, RevisionView, SearchResponse } from "@/lib/api/types";
import { current, initialRoom, phaseOf, roomReducer, type RoomState } from "./room";

const demo = fixtures.demo as unknown as DemoPayload;
const shocked = fixtures.shocked as unknown as RevisionView;
const search = fixtures.search as unknown as SearchResponse;

const booted = (): RoomState => roomReducer(initialRoom, { type: "booted", demo, health: null });
const ev = (seq: number, type: AgentEvent["type"], data: Record<string, unknown>): AgentEvent => ({ seq, type, at_ms: seq * 10, data });

describe("room reducer", () => {
  it("boots into a verified ready plan", () => {
    const s = booted();
    expect(phaseOf(s)).toBe("ready");
    expect(current(s)?.revision.id).toBe(demo.initial.revision.id);
  });

  it("moves to impact on shock and bumps the ripple key", () => {
    const s = roomReducer(booted(), { type: "shocked", view: shocked });
    expect(phaseOf(s)).toBe("impact");
    expect(s.history).toHaveLength(2);
    expect(s.rippleKey).toBe(1);
  });

  it("tracks a live run through to verified options", () => {
    let s = roomReducer(booted(), { type: "shocked", view: shocked });
    s = roomReducer(s, { type: "runStarted", source: "nemotron" });
    expect(phaseOf(s)).toBe("running");
    s = roomReducer(s, { type: "runEvent", event: ev(1, "run_started", { provider: "nebius-token-factory", model: "nvidia/x", live: true }) });
    expect(s.run.provider?.live).toBe(true);
    const option = { candidate_id: "c2", title: "Rent a trolley", why: "Parallel unloads.", evaluation: search.options[0]!.evaluation };
    s = roomReducer(s, { type: "runEvent", event: ev(2, "options", { options: [option], finalized_by_model: true, summary: "One option." }) });
    s = roomReducer(s, { type: "runEvent", event: ev(3, "done", { stop_reason: "submitted" }) });
    expect(phaseOf(s)).toBe("options");
    expect(s.run.options[0]).toMatchObject({ id: "c2", source: "nemotron", baseRevisionId: shocked.revision.id });
    expect(s.previewId).toBe("c2");
  });

  it("marks a run failed when the provider errors and nothing was found", () => {
    let s = roomReducer(booted(), { type: "shocked", view: shocked });
    s = roomReducer(s, { type: "runStarted", source: "nemotron" });
    s = roomReducer(s, { type: "runEvent", event: ev(1, "error", { code: "CREDIT_EXHAUSTED", message: "No credits." }) });
    s = roomReducer(s, { type: "runEvent", event: ev(2, "options", { options: [], finalized_by_model: false }) });
    s = roomReducer(s, { type: "runEvent", event: ev(3, "done", {}) });
    expect(s.run.status).toBe("failed");
    expect(s.run.error?.code).toBe("CREDIT_EXHAUSTED");
  });

  it("undo walks back through verified history and reset returns to the seed", () => {
    let s = roomReducer(booted(), { type: "shocked", view: shocked });
    s = roomReducer(s, { type: "undo" });
    expect(current(s)?.revision.id).toBe(demo.initial.revision.id);
    s = roomReducer(s, { type: "undo" });
    expect(s.history).toHaveLength(1);
    s = roomReducer(roomReducer(s, { type: "shocked", view: shocked }), { type: "reset" });
    expect(s.history).toHaveLength(1);
    expect(phaseOf(s)).toBe("ready");
  });
});
