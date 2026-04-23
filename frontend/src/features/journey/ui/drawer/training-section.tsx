"use client";

/**
 * Training section — pins with `mode === "training"`, ordered by
 * `training_step_order` (Req 5.1, 5.4). Collapsed by default via a
 * native <details> element so SSR rendering remains testable without a
 * DOM (the pattern shadcn's Collapsible uses requires Radix Portal, which
 * doesn't SSR cleanly).
 */

import type { JourneyNodeDetail, JourneyPin } from "@/entities/journey";

function sortTrainingPins(pins: readonly JourneyPin[]): JourneyPin[] {
  return pins
    .filter((p) => p.mode === "training")
    .slice()
    .sort((a, b) => {
      const ao = a.training_step_order ?? Number.POSITIVE_INFINITY;
      const bo = b.training_step_order ?? Number.POSITIVE_INFINITY;
      return ao - bo;
    });
}

export interface TrainingSectionProps {
  readonly detail: JourneyNodeDetail;
}

export function TrainingSection({ detail }: TrainingSectionProps) {
  const steps = sortTrainingPins(detail.pins);
  return (
    <section
      data-testid="training-section"
      className="p-4"
      aria-label="Шаги обучения"
    >
      <details>
        <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-text-subtle">
          Шаги обучения ({steps.length})
        </summary>
        <div className="mt-2">
          {steps.length === 0 ? (
            <p className="text-xs text-text-subtle">
              Шаги обучения ещё не заданы
            </p>
          ) : (
            <ol className="space-y-1.5">
              {steps.map((pin, idx) => (
                <li
                  key={pin.id}
                  className="flex gap-2 text-xs text-text"
                >
                  <span className="w-5 shrink-0 text-text-subtle">
                    {pin.training_step_order ?? idx + 1}.
                  </span>
                  <span>{pin.expected_behavior}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </details>
    </section>
  );
}
