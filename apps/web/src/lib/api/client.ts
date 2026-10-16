import type { DemoPayload, Evaluation, Health, Patch, Plan, Revision, RevisionView, SearchResponse } from "./types";

/** Empty in production (same origin as FastAPI). Set NEXT_PUBLIC_API_BASE for local dev. */
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function toApiError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: { code?: string; message?: string; details?: unknown } };
    if (body.error?.code) return new ApiError(res.status, body.error.code, body.error.message ?? res.statusText, body.error.details);
  } catch {
    // Non-JSON error body (proxy or platform page): fall through to a generic error.
  }
  return new ApiError(res.status, res.status >= 500 ? "INTERNAL" : "HTTP_ERROR", `Request failed (${res.status}).`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Cannot reach the Ripple Room server. Check your connection and retry.");
  }
  if (!res.ok) throw await toApiError(res);
  return (await res.json()) as T;
}

const post = <T>(path: string, body: unknown, signal?: AbortSignal) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body), signal });

export const api = {
  health: () => request<Health>("/api/health"),
  demo: () => request<DemoPayload>("/api/demo"),
  shock: (revision: Revision, presetId: string) => post<RevisionView>("/api/shock", { revision, preset_id: presetId }),
  evaluate: (revision: Revision, patch: Patch) => post<Evaluation>("/api/evaluate", { revision, patch }),
  search: (revision: Revision) => post<SearchResponse>("/api/search", { revision }),
  apply: (revision: Revision, baseRevisionId: string, patch: Patch, plan: Plan) =>
    post<RevisionView>("/api/apply", { revision, base_revision_id: baseRevisionId, patch, plan }),
};
