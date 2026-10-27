"use client";

import { useEffect, useRef, useState } from "react";
import { motionReduced } from "./useReducedMotion";

/**
 * Animate a number towards `target` with an ease-out curve. Under
 * reduced motion (or with no previous value) it jumps straight there.
 * All state updates happen in animation-frame callbacks, never synchronously in the effect.
 */
export function useTween(target: number | null, ms = 900): number | null {
  const [value, setValue] = useState(target);
  const shown = useRef(target);
  useEffect(() => {
    const start = shown.current;
    const instant =
      target == null || start == null || start === target || motionReduced();
    let frame = 0;
    const t0 = performance.now();
    const step = (now: number) => {
      const k = instant ? 1 : Math.min(1, (now - t0) / ms);
      const eased = 1 - Math.pow(1 - k, 3);
      const next = target == null || start == null ? target : Math.round(start + (target - start) * eased);
      shown.current = next;
      setValue(next);
      if (k < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, ms]);
  return value;
}
