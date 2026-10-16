"use client";

import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import { api, ApiError } from "@/lib/api/client";
import { streamRecover } from "@/lib/api/sse";
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
        await streamRecover(view.revision, priorities, (event) => dispatch({ type: "runEvent", event }), controller.signal);
      } catch (err) {
        if (!controller.signal.aborted) dispatch({ type: "runFailed", error: asError(err) });
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
      const res = await api.search(view.revision);
      const options: RecoveryOption[] = res.options.map((o) => ({
        id: o.id,
        title: o.menu_items.length ? o.menu_items.map((m) => m.label).join(" + ") : "No change needed",
        why: null,
        source: "search",
        baseRevisionId: res.base_revision_id,
        evaluation: o.evaluation,
      }));
      dispatch({ type: "searchDone", options: options.slice(0, 4) });
    } catch (err) {
      dispatch({ type: "failed", error: asError(err) });
    }
  }, [view]);

  const apply = useCallback(
    async (option: RecoveryOption) => {
      if (!view || !option.evaluation.plan) return;
      dispatch({ type: "pending", pending: "apply" });
      try {
        const next = await api.apply(view.revision, option.baseRevisionId, option.evaluation.patch, option.evaluation.plan);
        dispatch({ type: "applied", view: next, title: option.title });
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
