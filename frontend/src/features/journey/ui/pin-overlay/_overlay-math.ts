/**
 * Pure helpers for the Task 22 pin overlay.
 *
 * Positioning is rel-coord based: every pin stores `last_rel_*` fractions
 * in [0.0, 1.0] of the screenshot's viewport. At render time we multiply by
 * the container's live size to get absolute px.
 *
 * Keeping these pure means we test without a DOM (the workspace ships no
 * jsdom). The React surface (`annotated-screen.tsx`) only handles wiring.
 *
 * Reqs: 8.3 (relative-coord overlay), 8.4 (broken flag), 8.6 (popover),
 * 8.7 (list surface), 14.4 (pending pins stay in list, off-overlay).
 */

import type { JourneyPin } from "@/entities/journey";

// ---------------------------------------------------------------------------
// Absolute-position computation
// ---------------------------------------------------------------------------

export interface RelRect {
  readonly rel_x: number;
  readonly rel_y: number;
  readonly rel_width: number;
  readonly rel_height: number;
}

export interface ContainerSize {
  readonly width: number;
  readonly height: number;
}

export interface AbsRect {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

function clamp01(value: number, label: string): number {
  if (value < 0) {
    console.warn(
      `[pin-overlay] ${label}=${value} out of range; clamping to 0`,
    );
    return 0;
  }
  if (value > 1) {
    console.warn(
      `[pin-overlay] ${label}=${value} out of range; clamping to 1`,
    );
    return 1;
  }
  return value;
}

/**
 * Multiply rel-coords by container size to get px. Defensive: clamps any
 * rel value outside [0, 1] (backend migration 283 enforces the range via
 * CHECK, but bad payloads should not crash the UI).
 */
export function computePinAbsolutePosition(
  rel: RelRect,
  container: ContainerSize,
): AbsRect {
  const w = container.width;
  const h = container.height;
  const rx = clamp01(rel.rel_x, "rel_x");
  const ry = clamp01(rel.rel_y, "rel_y");
  const rw = clamp01(rel.rel_width, "rel_width");
  const rh = clamp01(rel.rel_height, "rel_height");
  return {
    x: rx * w,
    y: ry * h,
    width: rw * w,
    height: rh * h,
  };
}

// ---------------------------------------------------------------------------
// Partition + classify
// ---------------------------------------------------------------------------

function hasBbox(pin: JourneyPin): boolean {
  return (
    pin.last_rel_x !== null &&
    pin.last_rel_y !== null &&
    pin.last_rel_width !== null &&
    pin.last_rel_height !== null
  );
}

/**
 * Split pins into positioned and pending. Pending pins (any rel-coord is
 * null) are listed in the drawer but not drawn on the overlay (Req 14.4).
 */
export function partitionPinsByBbox(pins: readonly JourneyPin[]): {
  withBbox: readonly JourneyPin[];
  pending: readonly JourneyPin[];
} {
  const withBbox: JourneyPin[] = [];
  const pending: JourneyPin[] = [];
  for (const pin of pins) {
    if (hasBbox(pin)) withBbox.push(pin);
    else pending.push(pin);
  }
  return { withBbox, pending };
}

export type PinBadgeState = "broken" | "pending" | "ok";

/**
 * Visual state of a pin:
 *   - `broken`  — Playwright could not resolve the selector (Req 8.4)
 *   - `pending` — selector OK but no nightly position yet (Req 14.4)
 *   - `ok`      — selector resolved, position cached
 *
 * `broken` wins over `pending` — a broken selector is a higher-priority
 * signal (the pin is unusable until the writer fixes it).
 */
export function classifyPinBadgeState(pin: JourneyPin): PinBadgeState {
  if (pin.selector_broken) return "broken";
  if (!hasBbox(pin)) return "pending";
  return "ok";
}
