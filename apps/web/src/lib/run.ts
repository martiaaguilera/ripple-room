import type { AgentEvent } from "./api/sse";

/** The agent loop's phases in the order they normally happen. Verify and revise may alternate. */
export const RUN_PHASES = ["perceive", "diagnose", "plan", "verify", "revise", "present"] as const;
export type RunPhase = (typeof RUN_PHASES)[number];

export interface RunProgress {
  visited: Set<string>;
  current: string | null;
  /** Model calls (or scripted steps for the simulated agent) the server reported. */
  steps: number;
  /** Proposals the verifier has judged, and how many of them hold. */
  checked: number;
  holds: number;
  latest: { name: string; summary: string; ok: boolean } | null;
}

/** Everything here is counted from server events; nothing is estimated. */
export function runProgress(events: AgentEvent[]): RunProgress {
  const visited = new Set<string>();
  let current: string | null = null;
  let steps = 0;
  let checked = 0;
  let holds = 0;
  let latest: RunProgress["latest"] = null;
  for (const e of events) {
    switch (e.type) {
      case "phase":
        current = String(e.data.name);
        visited.add(current);
        break;
      case "model_call":
        steps += 1;
        break;
      case "candidate": {
        checked += 1;
        const ev = e.data.evaluation as { status?: string } | undefined;
        if (ev?.status === "verified") holds += 1;
        break;
      }
      case "tool_result":
        latest = { name: String(e.data.name), summary: String(e.data.summary ?? ""), ok: Boolean(e.data.ok) };
        break;
      default:
        break;
    }
  }
  return { visited, current, steps, checked, holds, latest };
}
