import { z } from "zod";
import { API_BASE, ApiError, toApiError } from "./client";
import type { Preferences, Revision } from "./types";

export const agentEventSchema = z.object({
  seq: z.number().int(),
  type: z.enum(["run_started", "phase", "model_call", "tool_call", "tool_result", "candidate", "options", "error", "done"]),
  at_ms: z.number(),
  data: z.record(z.string(), z.unknown()),
});

export type AgentEvent = z.infer<typeof agentEventSchema>;

/** Parse one SSE frame ("event: x\ndata: {...}"). Returns null for comments/keep-alives. */
export function parseFrame(frame: string): AgentEvent | null {
  const data = frame
    .split("\n")
    .filter((l) => l.startsWith("data:"))
    .map((l) => l.slice(5).trimStart())
    .join("\n");
  if (!data) return null;
  return agentEventSchema.parse(JSON.parse(data));
}

/** POST /api/recover and invoke `onEvent` for every server event until the run ends. */
export async function streamRecover(
  revision: Revision,
  priorities: string,
  preferences: Preferences,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/recover`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify({ revision, priorities, preferences }),
      signal,
    });
  } catch {
    if (signal?.aborted) return;
    throw new ApiError(0, "NETWORK", "Cannot reach the Ripple Room server. Check your connection and retry.");
  }
  if (!res.ok || !res.body) throw await toApiError(res);
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let finished = false;
  const emit = (event: AgentEvent) => {
    if (event.type === "done") finished = true;
    onEvent(event);
  };
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n/g, "\n");
    let cut = buffer.indexOf("\n\n");
    while (cut !== -1) {
      const event = parseFrame(buffer.slice(0, cut));
      buffer = buffer.slice(cut + 2);
      if (event) emit(event);
      cut = buffer.indexOf("\n\n");
    }
  }
  const tail = parseFrame(buffer.trim());
  if (tail) emit(tail);
  // A run always ends with "done"; without it the connection was cut (proxy or platform timeout).
  if (!finished && !signal?.aborted) {
    throw new ApiError(
      0,
      "STREAM_CUT",
      "The connection closed before the run finished. Nothing was changed; retry or use the playbook search.",
    );
  }
}
