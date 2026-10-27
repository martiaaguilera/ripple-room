"use client";

import { useSyncExternalStore } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";
const KEY = "rr-motion";

/** What the viewer chose in the app, if anything. `null` means "follow the system setting". */
export type MotionOverride = "full" | "reduce" | null;

export interface MotionState {
  /** Motion is reduced right now (system setting, unless the viewer overrode it). */
  reduced: boolean;
  /** The operating system or browser asks for reduced motion. */
  system: boolean;
  override: MotionOverride;
}

const listeners = new Set<() => void>();
/** Fallback when storage is blocked (private window): the choice lasts until reload. */
let memory: MotionOverride = null;

function readOverride(): MotionOverride {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "full" || v === "reduce" ? v : null;
  } catch {
    return memory;
  }
}

let cached: MotionState | null = null;

function compute(): MotionState {
  const system = window.matchMedia(QUERY).matches;
  const override = readOverride();
  const reduced = override ? override === "reduce" : system;
  if (!cached || cached.reduced !== reduced || cached.system !== system || cached.override !== override) {
    cached = { reduced, system, override };
  }
  return cached;
}

function apply(): void {
  document.documentElement.dataset.motion = compute().reduced ? "reduce" : "full";
  for (const l of listeners) l();
}

function subscribe(onChange: () => void): () => void {
  const mql = window.matchMedia(QUERY);
  listeners.add(onChange);
  mql.addEventListener("change", apply);
  return () => {
    listeners.delete(onChange);
    mql.removeEventListener("change", apply);
  };
}

const SERVER: MotionState = { reduced: false, system: false, override: null };

/** Motion preference: the system setting, unless the viewer chose otherwise in the app. */
export function useMotion(): MotionState {
  return useSyncExternalStore(subscribe, compute, () => SERVER);
}

/** True when animations should be skipped. Server render assumes motion is allowed. */
export function useReducedMotion(): boolean {
  return useMotion().reduced;
}

/** Non-hook read for animation loops. */
export function motionReduced(): boolean {
  return compute().reduced;
}

/** Remember the viewer's choice in this browser only; `null` goes back to the system setting. */
export function setMotionOverride(next: MotionOverride): void {
  memory = next;
  try {
    if (next) window.localStorage.setItem(KEY, next);
    else window.localStorage.removeItem(KEY);
  } catch {
    // Storage blocked: `memory` carries the choice for this page load.
  }
  apply();
}

/**
 * Runs in <head> before first paint, so CSS can key off `data-motion` without a flash of motion.
 * Kept in sync with `compute()` above.
 */
export const MOTION_BOOT = `(function(){var d=document.documentElement,r;try{var o=localStorage.getItem("${KEY}");r=o==="reduce"||(o!=="full"&&matchMedia("${QUERY}").matches)}catch(e){r=matchMedia("${QUERY}").matches}d.dataset.motion=r?"reduce":"full"})()`;
