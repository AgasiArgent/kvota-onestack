"use client";

/**
 * Left pane of the flow runner — a vertical numbered list of steps with the
 * current step highlighted. Clicking a row calls `onJumpTo(index)`.
 *
 * Req 18.4 — "left = step list (numbered 1–N, current step highlighted)".
 *
 * The pure `formatStepLabel` helper is exported so the unit test can assert
 * the label format without rendering the component.
 */

import type { JourneyFlowStep } from "@/entities/journey";

// ---------------------------------------------------------------------------
// Pure helper — exported for unit tests.
// ---------------------------------------------------------------------------

/**
 * Label for a single step row, e.g. `"3. Проверить customer"`. Index is
 * zero-based; the label is 1-based for human readability.
 */
export function formatStepLabel(step: JourneyFlowStep, index: number): string {
  return `${index + 1}. ${step.action}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  readonly steps: readonly JourneyFlowStep[];
  readonly activeIndex: number;
  readonly onJumpTo: (index: number) => void;
}

export function FlowStepList({ steps, activeIndex, onJumpTo }: Props) {
  return (
    <nav
      aria-label="Шаги пути"
      data-testid="journey-flow-step-list"
      className="flex flex-col gap-1 border-r border-border-light bg-surface-muted/40 p-3"
    >
      <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-text-subtle">
        Шаги
      </div>
      <ol className="flex flex-col gap-1">
        {steps.map((step, index) => {
          const isActive = index === activeIndex;
          return (
            <li key={`${step.node_id}-${index}`}>
              <button
                type="button"
                aria-current={isActive ? "step" : undefined}
                data-testid={`journey-flow-step-${index}`}
                onClick={() => onJumpTo(index)}
                className={[
                  "flex w-full flex-col gap-0.5 rounded-md border px-3 py-2 text-left text-sm",
                  "transition-colors",
                  isActive
                    ? "border-l-4 border-l-accent border-y-border-light border-r-border-light bg-background font-semibold text-text-default"
                    : "border-border-light bg-background/50 text-text-subtle hover:border-border-strong hover:text-text-default",
                ].join(" ")}
              >
                <span className="truncate">{formatStepLabel(step, index)}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
