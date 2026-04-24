"use client";

/**
 * Flow runner state — manages `stepIndex`, keyboard navigation, and the
 * "exit to canvas" callback. Pure helpers (`clampStepIndex`,
 * `resolveKeyAction`) live at module scope for unit-testing without
 * mounting the hook.
 *
 * Req 18.6 — "Navigation between steps SHALL support keyboard (← →, Esc to
 * exit flow back to canvas) and explicit Next/Prev buttons."
 *
 * FSD boundary: `features/journey/lib/` — no imports from other features.
 */

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit tests.
// ---------------------------------------------------------------------------

/**
 * Clamp a requested step index into `[0, stepCount - 1]`.
 * If `stepCount <= 0`, the only sensible index is 0 (the caller typically
 * renders an empty-flow fallback instead of a step).
 */
export function clampStepIndex(requested: number, stepCount: number): number {
  if (stepCount <= 0) return 0;
  if (requested < 0) return 0;
  if (requested >= stepCount) return stepCount - 1;
  return requested;
}

/** Keyboard action resolved from a `KeyboardEvent.key`. */
export type FlowKeyAction = "next" | "prev" | "exit";

/**
 * Map a `KeyboardEvent.key` value to a flow-navigation action, or `null` if
 * the key is not a bound shortcut. Kept pure so the test suite doesn't need
 * to synthesise KeyboardEvents.
 */
export function resolveKeyAction(key: string): FlowKeyAction | null {
  if (key === "ArrowRight") return "next";
  if (key === "ArrowLeft") return "prev";
  if (key === "Escape") return "exit";
  return null;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface UseFlowStateArgs {
  readonly stepCount: number;
  readonly onExit: (lastNodeId: string | null) => void;
  /**
   * Resolve the node_id for a given step index. Called at exit time so the
   * hook can pass the CURRENT step's node_id (not the starting one) to
   * `onExit`. Provided by the caller because only it knows the step → node_id
   * mapping.
   */
  readonly resolveNodeId: (index: number) => string | null;
}

interface UseFlowStateResult {
  readonly stepIndex: number;
  readonly next: () => void;
  readonly prev: () => void;
  readonly jumpTo: (index: number) => void;
  readonly exit: () => void;
}

/**
 * Hook that owns the `stepIndex` state + wires keyboard listeners. The
 * caller renders step UI; the hook only manages navigation.
 */
export function useFlowState({
  stepCount,
  onExit,
  resolveNodeId,
}: UseFlowStateArgs): UseFlowStateResult {
  const [stepIndex, setStepIndex] = useState(0);

  const jumpTo = useCallback(
    (index: number) => {
      setStepIndex(() => clampStepIndex(index, stepCount));
    },
    [stepCount]
  );

  const next = useCallback(() => {
    setStepIndex((prev) => clampStepIndex(prev + 1, stepCount));
  }, [stepCount]);

  const prev = useCallback(() => {
    setStepIndex((prev) => clampStepIndex(prev - 1, stepCount));
  }, [stepCount]);

  const exit = useCallback(() => {
    // Read the LATEST stepIndex via the state updater pattern so the closure
    // doesn't capture a stale value. `setStepIndex` returns the same index
    // (no-op write) but gives us a hook into the current state.
    setStepIndex((current) => {
      onExit(resolveNodeId(current));
      return current;
    });
  }, [onExit, resolveNodeId]);

  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      // Don't hijack keys while the user is typing in an input/textarea.
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      const action = resolveKeyAction(event.key);
      if (action === null) return;
      event.preventDefault();
      if (action === "next") next();
      else if (action === "prev") prev();
      else if (action === "exit") exit();
    }
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
    };
  }, [next, prev, exit]);

  return { stepIndex, next, prev, jumpTo, exit };
}
