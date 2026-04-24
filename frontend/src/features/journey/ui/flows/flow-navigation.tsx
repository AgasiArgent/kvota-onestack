"use client";

/**
 * Right pane of the flow runner — step counter, persona metadata, and
 * explicit Prev/Next/Exit buttons. Keyboard bindings live in
 * `useFlowState`; this component is the mouse-driven equivalent.
 *
 * Req 18.6 — explicit "Next step" / "Previous step" buttons.
 * Req 18.7 — surface overall flow progress and estimated remaining time.
 */

import type { JourneyFlow } from "@/entities/journey";
import { formatRemainingMinutes } from "./flow-navigation-helpers";

interface Props {
  readonly flow: JourneyFlow;
  readonly stepIndex: number;
  readonly onPrev: () => void;
  readonly onNext: () => void;
  readonly onExit: () => void;
}

export function FlowNavigation({
  flow,
  stepIndex,
  onPrev,
  onNext,
  onExit,
}: Props) {
  const stepCount = flow.steps.length;
  const isFirst = stepIndex <= 0;
  const isLast = stepIndex >= stepCount - 1;
  const remainingMinutes = formatRemainingMinutes(
    flow.est_minutes,
    stepIndex,
    stepCount
  );

  return (
    <aside
      data-testid="journey-flow-navigation"
      aria-label="Навигация по пути"
      className="flex flex-col gap-4 border-l border-border-light bg-surface-muted/40 p-4"
    >
      <div className="flex flex-col gap-1">
        <div className="text-[11px] font-medium uppercase tracking-wide text-text-subtle">
          Прогресс
        </div>
        <div
          data-testid="journey-flow-step-counter"
          className="text-2xl font-semibold text-text-default"
        >
          {stepIndex + 1} / {stepCount}
        </div>
        <div className="text-xs text-text-subtle">
          Осталось ~{remainingMinutes} мин
        </div>
      </div>

      <div className="flex flex-col gap-1 rounded-md border border-border-light bg-background p-3">
        <div className="text-[11px] font-medium uppercase tracking-wide text-text-subtle">
          Персона
        </div>
        <div className="text-sm font-medium text-text-default">
          {flow.persona}
        </div>
        {flow.description ? (
          <p className="mt-1 text-xs text-text-subtle">{flow.description}</p>
        ) : null}
      </div>

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={onPrev}
          disabled={isFirst}
          data-testid="journey-flow-prev-btn"
          className="rounded-md border border-border-light bg-background px-3 py-2 text-sm font-medium text-text-default transition-colors hover:border-border-strong disabled:cursor-not-allowed disabled:opacity-50"
        >
          ← Назад
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={isLast}
          data-testid="journey-flow-next-btn"
          className="rounded-md border border-accent bg-accent px-3 py-2 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Далее →
        </button>
        <button
          type="button"
          onClick={onExit}
          data-testid="journey-flow-exit-btn"
          className="mt-2 rounded-md border border-border-light bg-background px-3 py-2 text-sm font-medium text-text-subtle transition-colors hover:border-border-strong hover:text-text-default"
        >
          Выйти (Esc)
        </button>
      </div>
    </aside>
  );
}
