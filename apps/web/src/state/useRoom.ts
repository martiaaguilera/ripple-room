"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import { api, ApiError } from "@/lib/api/client";
import { streamRecover } from "@/lib/api/sse";
import type { Interpretation, Preferences } from "@/lib/api/types";
import { buildRoomView } from "@/lib/viewmodel";
import { current, initialRoom, phaseOf, roomReducer, type RecoveryOption } from "./room";

const asError = (err: unknown) =>
  err instanceof ApiError
    ? { code: err.code, message: err.message }
    : { code: "CLIENT", message: err instanceof Error ? err.message : "Unexpected error." };

export function useRoom() {
  const [state, dispatch] = useReducer(roomReducer, initialRoom);
  const abortRef = useRef<AbortController | null>(null);

  const boot = useCallback(async () => {
    try {
      const [demo, health] = await Promise.all([api.demo(), api.health().catch(() => null)]);
      dispatch({ type: "booted", demo, health });
    } catch (err) {
      dispatch({ type: "failed", error: asError(err) });
    }
  }, []);

  useEffect(() => {
    void boot();
    return () => abortRef.current?.abort();
  }, [boot]);

  const view = current(state);
  const phase = phaseOf(state);
  const preview = state.run.options.find((o) => o.id === state.previewId) ?? null;
  const room = useMemo(
    () => (state.demo && view ? buildRoomView(state.demo.scenario, view, preview?.evaluation ?? null) : null),
    [state.demo, view, preview],
  );

  const shock = useCallback(
    async (presetId: string) => {
      if (!view) return;
      abortRef.current?.abort();
      dispatch({ type: "pending", pending: "shock" });
      try {
        dispatch({ type: "shocked", view: await api.shock(view.revision, presetId) });
      } catch (err) {
        dispatch({ type: "failed", error: asError(err) });
      }
    },
    [view],
  );

  const recover = useCallback(
    async (priorities: string) => {
      if (!view) return;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      dispatch({ type: "runStarted", source: "nemotron" });
      try {
        await streamRecover(
          view.revision,
          priorities,
          state.preferences,
          (event) => dispatch({ type: "runEvent", event }),
          controller.signal,
        );
      } catch (err) {
        if (!controller.signal.aborted) {
          const error = asError(err);
          dispatch({ type: "runFailed", error });
          // The server just told us live AI is off: refresh the badge so the UI stops implying it is live.
          if (["AI_PAUSED", "AI_BUDGET_EXHAUSTED", "MODEL_UNAVAILABLE"].includes(error.code)) {
            void api.health().then((health) => dispatch({ type: "health", health }), () => undefined);
          }
        }
      }
    },
    [view, state.preferences],
  );

  const interpret = useCallback(
    async (text: string) => {
      if (!view) return;
      dispatch({ type: "intakeStarted", text });
      try {
        dispatch({ type: "intakeDone", result: await api.interpret(view.revision, text) });
      } catch (err) {
        dispatch({ type: "intakeFailed", error: asError(err).message });
      }
    },
    [view],
  );

  /** Apply the confirmed incidents one by one (each becomes its own verified revision). */
  const confirmIntake = useCallback(
    async (result: Interpretation, preferences: Preferences) => {
      if (!view) return;
      dispatch({ type: "setPreferences", preferences });
      dispatch({ type: "pending", pending: "shock" });
      let revision = view.revision;
      try {
        for (const incident of result.incidents) {
          const next = await api.shockTyped(revision, incident.shock);
          dispatch({ type: "shocked", view: next });
          revision = next.revision;
        }
        dispatch({ type: "pending", pending: null });
        dispatch({ type: "intakeCleared" });
      } catch (err) {
        dispatch({ type: "failed", error: asError(err) });
      }
    },
    [view],
  );

  const cancelRun = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: "runFailed", error: { code: "CANCELLED", message: "Run stopped. Nothing was changed." } });
  }, []);

  const search = useCallback(async () => {
    if (!view) return;
    dispatch({ type: "pending", pending: "search" });
    try {
      const res = await api.search(view.revision, state.preferences);
      const options: RecoveryOption[] = res.options.map((o) => ({
        id: o.id,
        title: o.menu_items.length ? o.menu_items.map((m) => m.label).join(" + ") : "No change needed",
        why: null,
        source: "search",
        baseRevisionId: res.base_revision_id,
        evaluation: o.evaluation,
        rank: o.rank,
        modelRank: null,
        report: o.report,
        touched: [...o.touched],
        origin: "playbook" as const,
      }));
      dispatch({ type: "searchDone", options: options.slice(0, 4) });
    } catch (err) {
      dispatch({ type: "failed", error: asError(err) });
    }
  }, [view, state.preferences]);

  const apply = useCallback(
    async (option: RecoveryOption) => {
      if (!view || !option.evaluation.plan) return;
      dispatch({ type: "pending", pending: "apply" });
      try {
        const plan = option.evaluation.plan;
        // The notice diffs against the plan people currently hold, so it is computed on the pre-apply revision.
        const notice = await api.notice(view.revision, option.evaluation.patch, plan).catch(() => null);
        const next = await api.apply(view.revision, option.baseRevisionId, option.evaluation.patch, plan);
        dispatch({ type: "applied", view: next, title: option.title, notice });
      } catch (err) {
        dispatch({ type: "failed", error: asError(err) });
      }
    },
    [view],
  );

  return {
    state,
    view,
    phase,
    room,
    preview,
    actions: {
      shock,
      recover,
      interpret,
      confirmIntake,
      clearIntake: () => dispatch({ type: "intakeCleared" }),
      setPreferences: (preferences: Preferences) => dispatch({ type: "setPreferences", preferences }),
      cancelRun,
      search,
      apply,
      retryBoot: boot,
      preview: (id: string | null) => dispatch({ type: "preview", optionId: id }),
      undo: () => dispatch({ type: "undo" }),
      reset: () => {
        abortRef.current?.abort();
        dispatch({ type: "reset" });
      },
      focus: (taskId: string | null) => dispatch({ type: "focus", taskId }),
      dismissError: () => dispatch({ type: "dismissError" }),
    },
  };
}

export type Room = ReturnType<typeof useRoom>;
