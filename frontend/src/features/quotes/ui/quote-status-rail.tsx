"use client";

import { useRouter } from "next/navigation";
import { Check, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QuoteStep } from "@/entities/quote/types";

// ---------------------------------------------------------------------------
// Step definitions (ordered as they appear in the rail)
// ---------------------------------------------------------------------------

const STEPS: { key: QuoteStep; label: string }[] = [
  { key: "sales", label: "Продажи" },
  { key: "procurement", label: "Закупки" },
  { key: "logistics", label: "Логистика" },
  { key: "customs", label: "Таможня" },
  { key: "control", label: "Контроль" },
  { key: "cost-analysis", label: "Кост-анализ" },
];

const STEP_ORDER = new Map(STEPS.map((s, i) => [s.key, i]));

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface QuoteStatusRailProps {
  activeStep: QuoteStep;
  currentWorkflowStep: QuoteStep;
  allowedSteps: QuoteStep[];
  isAdmin: boolean;
  quoteId: string;
}

export function QuoteStatusRail({
  activeStep,
  currentWorkflowStep,
  allowedSteps,
  isAdmin,
  quoteId,
}: QuoteStatusRailProps) {
  const router = useRouter();
  const currentIdx = STEP_ORDER.get(currentWorkflowStep) ?? 0;

  function handleStepClick(stepKey: QuoteStep) {
    router.replace(`/quotes/${quoteId}?step=${stepKey}`, { scroll: false });
  }

  return (
    <nav
      className="w-24 shrink-0 border-l border-border py-4 px-2"
      aria-label="Этапы КП"
    >
      <ul className="flex flex-col gap-1">
        {STEPS.map((step) => {
          const stepIdx = STEP_ORDER.get(step.key) ?? 0;
          const isCompleted = stepIdx < currentIdx;
          const isCurrent = step.key === currentWorkflowStep;
          const isActive = step.key === activeStep;
          const isClickable = isAdmin || allowedSteps.includes(step.key);

          return (
            <li key={step.key}>
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => handleStepClick(step.key)}
                className={cn(
                  "flex items-center gap-2 w-full rounded-md px-2 py-1.5 text-left text-xs transition-colors",
                  isActive && "bg-accent/10",
                  isClickable
                    ? "cursor-pointer hover:bg-muted"
                    : "cursor-default opacity-60"
                )}
              >
                {/* Step indicator icon */}
                {isCompleted ? (
                  <Check size={14} className="text-success shrink-0" />
                ) : isCurrent ? (
                  <Circle
                    size={14}
                    className="text-accent fill-accent shrink-0"
                  />
                ) : (
                  <Circle size={14} className="text-text-subtle shrink-0" />
                )}

                {/* Step label */}
                <span
                  className={cn(
                    "leading-tight",
                    isCompleted && "text-text-muted",
                    isCurrent && "font-semibold text-foreground",
                    !isCompleted && !isCurrent && "text-text-muted"
                  )}
                >
                  {step.label}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
