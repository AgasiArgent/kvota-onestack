"use client";

/**
 * Pin-detail popover (Task 22 / Req 8.6).
 *
 * Stateless — the parent (`annotated-screen.tsx`) controls visibility via
 * `selectedPinId`. Positions itself below the pin's bbox; if that would
 * push it below the container, it flips above.
 */

import type { CSSProperties } from "react";

import type {
  JourneyNodeId,
  JourneyPin,
  RoleSlug,
} from "@/entities/journey";
import { Button } from "@/components/ui/button";
import type { AbsRect, PinBadgeState } from "./_overlay-math";
import { VerifyButtons } from "./verify-buttons";

export interface PinPopoverProps {
  readonly pin: JourneyPin;
  readonly rect: AbsRect;
  readonly state: PinBadgeState;
  readonly container: { readonly width: number; readonly height: number };
  readonly onClose: () => void;
  /** When provided, QA-mode pins render verify buttons inside the popover (Task 23). */
  readonly nodeId?: JourneyNodeId;
  readonly userId?: string;
  readonly userRoles?: readonly RoleSlug[];
}

const STATE_COPY: Record<PinBadgeState, string> = {
  ok: "Активен",
  broken: "Селектор сломан — обновите",
  pending: "Позиция не обновлена",
};

const MODE_COPY = {
  qa: "QA-пин",
  training: "Обучающий шаг",
} as const;

export function PinPopover({
  pin,
  rect,
  state,
  container,
  onClose,
  nodeId,
  userId,
  userRoles,
}: PinPopoverProps) {
  // Prefer below-the-bbox; flip above if there isn't room.
  const below = rect.y + rect.height + 140 < container.height;
  const style: CSSProperties = below
    ? {
        position: "absolute",
        top: rect.y + rect.height + 8,
        left: Math.min(rect.x, Math.max(0, container.width - 280)),
        width: 280,
      }
    : {
        position: "absolute",
        top: Math.max(0, rect.y - 148),
        left: Math.min(rect.x, Math.max(0, container.width - 280)),
        width: 280,
      };

  const updated = pin.last_position_update
    ? new Date(pin.last_position_update).toLocaleString("ru-RU")
    : "—";

  return (
    <div
      role="dialog"
      aria-label="Детали пина"
      data-testid="pin-popover"
      style={style}
      className="z-10 rounded-md border border-border-light bg-background p-3 text-xs shadow-md"
    >
      <div className="mb-1 flex items-center justify-between">
        <span className="font-semibold text-text">{MODE_COPY[pin.mode]}</span>
        <span
          data-testid="pin-popover-state"
          className={
            state === "broken"
              ? "text-destructive"
              : state === "pending"
                ? "text-text-subtle"
                : "text-text-muted"
          }
        >
          {STATE_COPY[state]}
        </span>
      </div>
      <p className="mb-2 text-text">{pin.expected_behavior}</p>
      <p className="mb-1 break-all font-mono text-[11px] text-text-subtle">
        {pin.selector}
      </p>
      <p className="mb-2 text-[11px] text-text-subtle">
        Обновлено: {updated}
      </p>
      {nodeId && userId && userRoles && (
        <div className="mb-2">
          <VerifyButtons
            pin={pin}
            nodeId={nodeId}
            userId={userId}
            userRoles={userRoles}
          />
        </div>
      )}
      <div className="flex justify-end">
        <Button
          size="sm"
          variant="outline"
          onClick={onClose}
          data-testid="pin-popover-close"
        >
          Закрыть
        </Button>
      </div>
    </div>
  );
}
