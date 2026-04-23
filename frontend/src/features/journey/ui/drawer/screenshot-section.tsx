"use client";

/**
 * Screenshot section (Req 5.1). Hidden for ghost nodes by the parent
 * (`shouldShowScreenshot`). The nightly Playwright pipeline (Req 10) will
 * populate the screenshot URL; for now we render a placeholder skeleton.
 *
 * DEBT: The drawer payload (`JourneyNodeDetail`) doesn't carry a
 * `screenshot_url` yet — that's delivered by the nightly pipeline in a
 * later task. Render a skeleton until the field is wired up.
 */

import type { JourneyNodeDetail } from "@/entities/journey";

export interface ScreenshotSectionProps {
  // Reserved for the nightly-screenshot payload once the pipeline wires it in.
  readonly detail: JourneyNodeDetail;
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function ScreenshotSection(_props: ScreenshotSectionProps) {
  return (
    <section
      data-testid="screenshot-section"
      className="p-4"
      aria-label="Скриншот"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
        Скриншот
      </h3>
      <div
        aria-hidden
        className="flex h-40 w-full items-center justify-center rounded-md border border-dashed border-border-light bg-background text-xs text-text-subtle"
      >
        Скриншот появится после nightly-прогона
      </div>
    </section>
  );
}
