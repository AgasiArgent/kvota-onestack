"use client";

/**
 * Annotated screenshot — Task 22.
 *
 * Renders the screenshot (or a placeholder when none is wired yet) and
 * overlays pin badges at positions derived from relative coordinates
 * (`last_rel_*`). ResizeObserver keeps the math in sync when the container
 * resizes.
 *
 * Pins without a resolved bbox are partitioned out (`partitionPinsByBbox`)
 * and surfaced by the drawer's pin-list instead (Req 14.4). Broken selectors
 * stay on the overlay but render in red (Req 8.4).
 *
 * Reqs: 8.3 (overlay), 8.4 (broken flag), 8.6 (popover), 8.7 (list), 14.4
 * (pending pin pipeline).
 */

import { useRef } from "react";

import type { JourneyPin } from "@/entities/journey";
import { useContainerSize } from "@/features/journey/lib/use-container-size";

import {
  classifyPinBadgeState,
  computePinAbsolutePosition,
  partitionPinsByBbox,
} from "./_overlay-math";
import { PinBadge } from "./pin-badge";
import { PinPopover } from "./pin-popover";

export interface AnnotatedScreenProps {
  readonly screenshotUrl: string | null;
  readonly pins: readonly JourneyPin[];
  readonly selectedPinId: string | null;
  readonly onPinClick: (pinId: string) => void;
}

export function AnnotatedScreen({
  screenshotUrl,
  pins,
  selectedPinId,
  onPinClick,
}: AnnotatedScreenProps) {
  const ref = useRef<HTMLDivElement>(null);
  const size = useContainerSize(ref);
  const { withBbox } = partitionPinsByBbox(pins);

  const selected =
    selectedPinId != null
      ? withBbox.find((p) => p.id === selectedPinId)
      : undefined;

  const selectedRect = selected
    ? computePinAbsolutePosition(
        {
          rel_x: selected.last_rel_x as number,
          rel_y: selected.last_rel_y as number,
          rel_width: selected.last_rel_width as number,
          rel_height: selected.last_rel_height as number,
        },
        size,
      )
    : null;

  return (
    <div
      ref={ref}
      data-testid="annotated-screen"
      aria-label="Аннотированный скриншот"
      className="relative w-full overflow-hidden rounded-md border border-border-light bg-background"
      // 16:10 aspect placeholder keeps the container measurable before the
      // real screenshot (with its own intrinsic size) is wired in.
      style={{ aspectRatio: "16 / 10" }}
    >
      {screenshotUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={screenshotUrl}
          alt=""
          className="absolute inset-0 h-full w-full object-contain"
        />
      ) : (
        <div
          aria-hidden
          className="absolute inset-0 flex items-center justify-center text-xs text-text-subtle"
        >
          Скриншот будет добавлен автоматически
        </div>
      )}

      {withBbox.map((pin, idx) => {
        const rect = computePinAbsolutePosition(
          {
            rel_x: pin.last_rel_x as number,
            rel_y: pin.last_rel_y as number,
            rel_width: pin.last_rel_width as number,
            rel_height: pin.last_rel_height as number,
          },
          size,
        );
        return (
          <PinBadge
            key={pin.id}
            pin={pin}
            index={idx}
            state={classifyPinBadgeState(pin)}
            selected={selectedPinId === pin.id}
            style={{
              left: rect.x,
              top: rect.y,
              width: rect.width,
              height: rect.height,
            }}
            onClick={onPinClick}
          />
        );
      })}

      {selected && selectedRect && (
        <PinPopover
          pin={selected}
          rect={selectedRect}
          state={classifyPinBadgeState(selected)}
          container={size}
          onClose={() => onPinClick(selected.id)}
        />
      )}
    </div>
  );
}
