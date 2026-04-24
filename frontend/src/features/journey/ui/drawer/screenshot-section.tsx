"use client";

/**
 * Screenshot section (Req 5.1). Hidden for ghost nodes by the parent
 * (`shouldShowScreenshot`). The nightly Playwright pipeline (Req 10) will
 * populate the screenshot URL; for now the drawer payload carries no
 * `screenshot_url`, so `AnnotatedScreen` renders its placeholder.
 *
 * Task 22 wires in the pin overlay: pins with resolved positions sit on
 * top of the screenshot (or placeholder) at rel-coord-derived px. Pins
 * without a bbox are surfaced by `pin-list-section` separately (Req 14.4).
 *
 * DEBT: `screenshot_url` still isn't on `JourneyNodeDetail` — `null` is
 * passed through until the nightly pipeline ships.
 */

import { useState } from "react";

import type { JourneyNodeDetail } from "@/entities/journey";
import { AnnotatedScreen } from "@/features/journey/ui/pin-overlay";

export interface ScreenshotSectionProps {
  readonly detail: JourneyNodeDetail;
}

export function ScreenshotSection({ detail }: ScreenshotSectionProps) {
  const [selectedPinId, setSelectedPinId] = useState<string | null>(null);

  const togglePin = (pinId: string) => {
    setSelectedPinId((current) => (current === pinId ? null : pinId));
  };

  return (
    <section
      data-testid="screenshot-section"
      className="p-4"
      aria-label="Скриншот"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
        Скриншот
      </h3>
      <AnnotatedScreen
        screenshotUrl={null}
        pins={detail.pins}
        selectedPinId={selectedPinId}
        onPinClick={togglePin}
      />
    </section>
  );
}
