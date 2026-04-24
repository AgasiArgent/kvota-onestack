"use client";

/**
 * Absolute-positioned pin badge rendered on top of a screenshot (Task 22).
 *
 * Shows an index number; colour reflects the pin's state
 * (`classifyPinBadgeState`):
 *   - `ok`      — primary fill
 *   - `broken`  — destructive fill + red ring, tooltip explains the break
 *   - `pending` — muted fill (rare; partitioned out by the parent but kept
 *                 for resilience)
 *
 * Selected badges get an extra outline ring so the user can tell which pin
 * the popover belongs to.
 */

import type { CSSProperties } from "react";

import type { JourneyPin } from "@/entities/journey";
import type { PinBadgeState } from "./_overlay-math";

export interface PinBadgeProps {
  readonly pin: JourneyPin;
  readonly index: number;
  readonly state: PinBadgeState;
  readonly selected: boolean;
  readonly style: CSSProperties;
  readonly onClick: (pinId: string) => void;
}

const STATE_CLASS: Record<PinBadgeState, string> = {
  ok: "bg-primary text-white ring-primary/40",
  broken: "bg-destructive text-white ring-destructive/60",
  pending: "bg-text-subtle text-white ring-text-subtle/40",
};

const STATE_LABEL: Record<PinBadgeState, string> = {
  ok: "Пин",
  broken: "Селектор сломан — обновите",
  pending: "Позиция не обновлена",
};

export function PinBadge({
  pin,
  index,
  state,
  selected,
  style,
  onClick,
}: PinBadgeProps) {
  // Anchor the badge at the top-left of its bbox and render a small circle
  // on the corner so it doesn't hide the element. Style.width/height drive a
  // bbox outline div; the clickable circle sits inside.
  const bbox: CSSProperties = {
    position: "absolute",
    left: style.left,
    top: style.top,
    width: style.width,
    height: style.height,
    pointerEvents: "none",
  };

  return (
    <div
      style={bbox}
      data-testid="pin-badge-bbox"
      className={`rounded-sm border-2 ${
        state === "broken"
          ? "border-destructive/70"
          : selected
            ? "border-primary"
            : "border-primary/40"
      }`}
    >
      <button
        type="button"
        onClick={() => onClick(pin.id)}
        aria-label={`${STATE_LABEL[state]}: ${pin.expected_behavior}`}
        title={`${pin.selector}\n${pin.expected_behavior.slice(0, 40)}${
          pin.expected_behavior.length > 40 ? "…" : ""
        }`}
        data-testid={`pin-badge-${pin.id}`}
        data-state={state}
        className={`pointer-events-auto absolute -left-3 -top-3 flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold ring-2 ${
          STATE_CLASS[state]
        } ${selected ? "outline outline-2 outline-primary outline-offset-1" : ""}`}
      >
        {index + 1}
      </button>
    </div>
  );
}
