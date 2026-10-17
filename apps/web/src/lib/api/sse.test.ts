import { afterEach, describe, expect, it, vi } from "vitest";
import fixtures from "@/test/fixtures.json";
import { defaultPreferences } from "@/state/room";
import type { DemoPayload } from "./types";
import { ApiError } from "./client";
import { streamRecover, type AgentEvent } from "./sse";

const revision = (fixtures as unknown as { demo: DemoPayload }).demo.initial.revision;

const frame = (seq: number, type: string, data: Record<string, unknown> = {}) =>
  `event: ${type}\ndata: ${JSON.stringify({ seq, type, at_ms: seq, data })}\n\n`;

function sseResponse(body: string): Response {
  return new Response(body, { status: 200, headers: { "content-type": "text/event-stream" } });
}

async function run(): Promise<{ events: AgentEvent[]; error: unknown }> {
  const events: AgentEvent[] = [];
  try {
    await streamRecover(revision, "", defaultPreferences, (e) => events.push(e));
    return { events, error: null };
  } catch (error) {
    return { events, error };
  }
}

afterEach(() => vi.unstubAllGlobals());

describe("streamRecover", () => {
  it("delivers every frame and resolves when the run says done", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frame(1, "run_started") + frame(2, "done"))));
    const { events, error } = await run();
    expect(error).toBeNull();
    expect(events.map((e) => e.type)).toEqual(["run_started", "done"]);
  });

  it("rejects a stream that closes before done, after delivering what arrived", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(frame(1, "run_started") + frame(2, "phase", { name: "plan" }))));
    const { events, error } = await run();
    expect(events.map((e) => e.type)).toEqual(["run_started", "phase"]);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("STREAM_CUT");
  });

  it("turns a failed fetch into a plain-language network error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    const { error } = await run();
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).code).toBe("NETWORK");
    expect((error as ApiError).message).toBe("Cannot reach the Ripple Room server. Check your connection and retry.");
  });

  it("maps a typed 503 refusal to its code and message", async () => {
    const body = { error: { code: "AI_PAUSED", message: "Live AI is paused by the operator.", details: null } };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(body), { status: 503 })));
    const { error } = await run();
    expect((error as ApiError).code).toBe("AI_PAUSED");
    expect((error as ApiError).message).toBe("Live AI is paused by the operator.");
  });
});
