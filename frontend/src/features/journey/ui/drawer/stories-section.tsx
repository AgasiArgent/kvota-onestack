"use client";

/**
 * Stories section — Req 5.1.
 *
 * DEBT: `JourneyNodeDetail` (from the Wave 4 backend DTO) only carries
 * `stories_count: number`, not the full story list. The full list lives on
 * `JourneyNode` in the manifest but isn't returned by `GET /api/journey/node/{id}`.
 * Until the backend adds a `stories: JourneyStory[]` field (or the UI reads
 * from the manifest directly), this section shows the count + a placeholder
 * link to the spec files where the stories live. Reported in resolution
 * summary.
 */

import type { JourneyNodeDetail } from "@/entities/journey";

export interface StoriesSectionProps {
  readonly detail: JourneyNodeDetail;
}

export function StoriesSection({ detail }: StoriesSectionProps) {
  const count = detail.stories_count;
  return (
    <section
      data-testid="stories-section"
      className="p-4"
      aria-label="Пользовательские истории"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
        Пользовательские истории
      </h3>
      {count === 0 ? (
        <p className="text-xs text-text-subtle">
          Пользовательские истории не привязаны
        </p>
      ) : (
        <p className="text-xs text-text-muted">
          Привязано историй: <span className="font-medium text-text">{count}</span>
          <span className="ml-2 text-text-subtle">
            (список появится после расширения API — см. Task 18 debt)
          </span>
        </p>
      )}
    </section>
  );
}
