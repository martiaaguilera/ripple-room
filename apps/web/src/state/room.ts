import type { AgentEvent } from "@/lib/api/sse";
import type { ChangeNotice, DemoPayload, Evaluation, Health, Interpretation, PreferenceReport, Preferences, RevisionView } from "@/lib/api/types";

/**
 * Journey: boot → ready → impact → running → options → (applied) ready.
 * History holds server-verified revisions only; undo pops, reset returns to the seed.
 */

export type OptionSource = "nemotron" | "mock" | "search";

export interface RecoveryOption {
  id: string;
  title: string;
  why: string | null;
  source: OptionSource;
  baseRevisionId: string;
  evaluation: Evaluation;
  rank: number;
  modelRank: number | null;
  report: PreferenceReport;
  touched: string[];
  /** model = proposed by the agent; playbook = deterministic search; no_change = keep the plan. */
  origin: "model" | "playbook" | "no_change";
}

export interface RunState {
  status: "idle" | "running" | "done" | "failed";
  source: OptionSource | null;
  events: AgentEvent[];
  options: RecoveryOption[];
  finalizedByModel: boolean | null;
  summary: string | null;
  error: { code: string; message: string } | null;
  provider: { name: string; model: string; live: boolean } | null;
}

export interface IntakeState {
  status: "idle" | "interpreting" | "ready" | "failed";
  text: string;
  result: Interpretation | null;
  error: string | null;
}

export interface RoomState {
  demo: DemoPayload | null;
  health: Health | null;
  history: RevisionView[];
  run: RunState;
  intake: IntakeState;
  preferences: Preferences;
  previewId: string | null;
  focusTaskId: string | null;
  pending: null | "shock" | "apply" | "search";
  error: { code: string; message: string } | null;
  lastAppliedTitle: string | null;
  notice: ChangeNotice | null;
  rippleKey: number;
}

export const defaultPreferences: Preferences = {
  guest_experience: "balanced",
  spend: "balanced",
  crew_stability: "balanced",
  budget_cap_cents: null,
  min_margin_minutes: 0,
  protected_tasks: [],
  source: "default",
  summary: "",
};

export const emptyRun: RunState = {
  status: "idle",
  source: null,
  events: [],
  options: [],
  finalizedByModel: null,
  summary: null,
  error: null,
  provider: null,
};

export const emptyIntake: IntakeState = { status: "idle", text: "", result: null, error: null };

export const initialRoom: RoomState = {
  demo: null,
  health: null,
  history: [],
  run: emptyRun,
  intake: emptyIntake,
  preferences: defaultPreferences,
  previewId: null,
  focusTaskId: null,
  pending: null,
  error: null,
  lastAppliedTitle: null,
  notice: null,
  rippleKey: 0,
};

export type RoomAction =
  | { type: "booted"; demo: DemoPayload; health: Health | null }
  | { type: "pending"; pending: RoomState["pending"] }
  | { type: "failed"; error: { code: string; message: string } }
  | { type: "dismissError" }
  | { type: "shocked"; view: RevisionView }
  | { type: "intakeStarted"; text: string }
  | { type: "intakeDone"; result: Interpretation }
  | { type: "intakeFailed"; error: string }
  | { type: "intakeCleared" }
  | { type: "setPreferences"; preferences: Preferences }
  | { type: "runStarted"; source: OptionSource }
  | { type: "runEvent"; event: AgentEvent }
  | { type: "runFailed"; error: { code: string; message: string } }
  | { type: "searchDone"; options: RecoveryOption[] }
  | { type: "preview"; optionId: string | null }
  | { type: "applied"; view: RevisionView; title: string; notice: ChangeNotice | null }
  | { type: "undo" }
  | { type: "reset" }
  | { type: "focus"; taskId: string | null }
  | { type: "health"; health: Health };

export const current = (s: RoomState): RevisionView | null => s.history[s.history.length - 1] ?? null;

export type Phase = "boot" | "ready" | "impact" | "running" | "options" | "applied";

export function phaseOf(s: RoomState): Phase {
  const view = current(s);
  if (!view) return "boot";
  if (s.run.status === "running") return "running";
  if (!view.verified) return s.run.options.length > 0 || s.run.status !== "idle" ? "options" : "impact";
  return view.revision.state.source === "apply" ? "applied" : "ready";
}

interface RawAgentOption {
  candidate_id: string;
  title: string;
  why: string;
  evaluation: Evaluation;
  rank: number;
  model_rank: number | null;
  report: PreferenceReport;
  touched: string[];
  origin?: "model" | "playbook" | "no_change";
}

function optionFromEvent(raw: unknown, source: OptionSource, baseRevisionId: string): RecoveryOption {
  const o = raw as RawAgentOption;
  return {
    id: o.candidate_id,
    title: o.title,
    why: o.why,
    source,
    baseRevisionId,
    evaluation: o.evaluation,
    rank: o.rank,
    modelRank: o.model_rank,
    report: o.report,
    touched: o.touched,
    origin: o.origin ?? "model",
  };
}

export function roomReducer(state: RoomState, action: RoomAction): RoomState {
  switch (action.type) {
    case "booted":
      return { ...initialRoom, demo: action.demo, health: action.health, history: [action.demo.initial] };
    case "pending":
      return { ...state, pending: action.pending, error: action.pending ? null : state.error };
    case "failed":
      return { ...state, pending: null, error: action.error };
    case "dismissError":
      return { ...state, error: null };
    case "shocked":
      return {
        ...state,
        pending: null,
        history: [...state.history, action.view],
        run: emptyRun,
        previewId: null,
        lastAppliedTitle: null,
        rippleKey: state.rippleKey + 1,
      };
    case "intakeStarted":
      return { ...state, intake: { status: "interpreting", text: action.text, result: null, error: null } };
    case "intakeDone":
      return { ...state, intake: { ...state.intake, status: "ready", result: action.result } };
    case "intakeFailed":
      return { ...state, intake: { ...state.intake, status: "failed", error: action.error } };
    case "intakeCleared":
      return { ...state, intake: emptyIntake };
    case "setPreferences":
      return { ...state, preferences: action.preferences };
    case "runStarted":
      return { ...state, run: { ...emptyRun, status: "running", source: action.source }, previewId: null, error: null };
    case "runEvent": {
      const run = { ...state.run, events: [...state.run.events, action.event] };
      const d = action.event.data;
      const base = current(state)?.revision.id ?? "";
      switch (action.event.type) {
        case "run_started":
          run.provider = { name: String(d.provider), model: String(d.model), live: Boolean(d.live) };
          run.source = d.live ? "nemotron" : "mock";
          break;
        case "options": {
          const src = run.source ?? "mock";
          run.options = ((d.options as unknown[]) ?? []).map((o) => optionFromEvent(o, src, base));
          run.finalizedByModel = Boolean(d.finalized_by_model);
          run.summary = (d.summary as string | null) ?? null;
          break;
        }
        case "error":
          run.error = { code: String(d.code), message: String(d.message) };
          break;
        case "done":
          run.status = run.error && run.options.length === 0 ? "failed" : "done";
          break;
      }
      const previewId = state.previewId ?? (action.event.type === "options" ? (run.options[0]?.id ?? null) : null);
      return { ...state, run, previewId };
    }
    case "runFailed":
      return { ...state, run: { ...state.run, status: "failed", error: action.error } };
    case "searchDone":
      return {
        ...state,
        pending: null,
        run: { ...emptyRun, status: "done", source: "search", options: action.options, finalizedByModel: null },
        previewId: action.options[0]?.id ?? null,
      };
    case "preview":
      return { ...state, previewId: action.optionId };
    case "applied":
      return {
        ...state,
        pending: null,
        history: [...state.history, action.view],
        run: emptyRun,
        previewId: null,
        lastAppliedTitle: action.title,
        notice: action.notice,
      };
    case "undo":
      if (state.history.length <= 1) return state;
      return { ...state, history: state.history.slice(0, -1), run: emptyRun, previewId: null, lastAppliedTitle: null, notice: null, error: null };
    case "reset":
      return state.demo ? { ...initialRoom, demo: state.demo, health: state.health, history: [state.demo.initial] } : state;
    case "focus":
      return { ...state, focusTaskId: action.taskId };
    case "health":
      return { ...state, health: action.health };
  }
}
