"use client";

/**
 * Pin-list section — QA pins with latest verification (Req 5.1).
 *
 * Hidden by the parent for ghost nodes. Verify buttons in Req 5.1 land in
 * a later task (Task 22 — verification flow); here we display the latest
 * verification result inline, read-only.
 */

import type {
  JourneyNodeDetail,
  JourneyPin,
  VerifyResult,
} from "@/entities/journey";

const RESULT_LABELS: Record<VerifyResult, string> = {
  verified: "Проверено",
  broken: "Сломано",
  skip: "Пропущено",
};

const RESULT_CLASS: Record<VerifyResult, string> = {
  verified: "bg-success-subtle text-success",
  broken: "bg-destructive/10 text-destructive",
  skip: "bg-background text-text-muted",
};

export interface PinListSectionProps {
  readonly detail: JourneyNodeDetail;
}

function qaPins(pins: readonly JourneyPin[]): JourneyPin[] {
  return pins.filter((p) => p.mode === "qa");
}

export function PinListSection({ detail }: PinListSectionProps) {
  const pins = qaPins(detail.pins);
  return (
    <section
      data-testid="pin-list-section"
      className="p-4"
      aria-label="QA-пины"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
        QA-пины ({pins.length})
      </h3>
      {pins.length === 0 ? (
        <p className="text-xs text-text-subtle">QA-пины ещё не созданы</p>
      ) : (
        <ul className="space-y-2">
          {pins.map((pin) => {
            const latest = detail.verifications_by_pin[pin.id];
            return (
              <li
                key={pin.id}
                className="rounded-md border border-border-light bg-background p-2 text-xs"
              >
                <p className="font-medium text-text">{pin.expected_behavior}</p>
                <p className="mt-1 break-all font-mono text-text-subtle">
                  {pin.selector}
                </p>
                {latest && (
                  <span
                    className={`mt-1 inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium ${RESULT_CLASS[latest.result]}`}
                  >
                    {RESULT_LABELS[latest.result]}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
