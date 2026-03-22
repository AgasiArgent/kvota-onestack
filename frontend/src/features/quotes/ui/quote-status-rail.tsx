"use client";

import { useRouter } from "next/navigation";
import { Check, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QuoteStep } from "@/entities/quote/types";

// ---------------------------------------------------------------------------
// Steps reflect the REAL business process sequence.
// "sales" appears twice: once at the start (filling items) and once at the
// end (calculation review + client negotiation).
// ---------------------------------------------------------------------------

interface StepDef {
  key: QuoteStep;
  label: string;
  /** Workflow statuses that map to this step being "current" */
  statuses: string[];
}

const STEPS: StepDef[] = [
  {
    key: "sales",
    label: "Заявка",
    statuses: ["draft"],
  },
  {
    key: "procurement",
    label: "Закупки",
    statuses: ["pending_procurement", "procurement_complete"],
  },
  {
    key: "logistics",
    label: "Логистика",
    statuses: ["pending_logistics"],
  },
  {
    key: "customs",
    label: "Таможня",
    statuses: ["pending_customs"],
  },
  {
    key: "calculation",
    label: "Расчёт",
    statuses: ["procurement_complete", "calculated", "pending_sales_review"],
  },
  {
    key: "control",
    label: "Контроль",
    statuses: [
      "pending_quote_control",
      "pending_spec_control",
      "pending_approval",
    ],
  },
  {
    key: "negotiation",
    label: "Переговоры",
    statuses: ["sent_to_client", "approved", "accepted"],
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface QuoteStatusRailProps {
  activeStep: QuoteStep;
  currentWorkflowStep: QuoteStep;
  allowedSteps: QuoteStep[];
  isAdmin: boolean;
  quoteId: string;
  workflowStatus: string;
}

export function QuoteStatusRail({
  activeStep,
  allowedSteps,
  isAdmin,
  quoteId,
  workflowStatus,
}: QuoteStatusRailProps) {
  const router = useRouter();

  // Find which step index the current workflow status maps to
  const currentStepIdx = STEPS.findIndex((s) =>
    s.statuses.includes(workflowStatus)
  );

  function handleStepClick(stepKey: QuoteStep) {
    router.replace(`/quotes/${quoteId}?step=${stepKey}`, { scroll: false });
  }

  return (
    <nav
      className="w-28 shrink-0 border-l border-border py-4 px-1"
      aria-label="Этапы КП"
    >
      <ul className="flex flex-col gap-0.5">
        {STEPS.map((step, idx) => {
          const isCompleted = currentStepIdx >= 0 && idx < currentStepIdx;
          const isCurrent = idx === currentStepIdx;
          const isActive = step.key === activeStep;
          const isClickable = isAdmin || allowedSteps.includes(step.key);

          return (
            <li key={`${step.key}-${idx}`}>
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => handleStepClick(step.key)}
                className={cn(
                  "flex items-center gap-2 w-full rounded-md px-2.5 py-2 text-left text-xs transition-colors",
                  isActive && "bg-accent/10",
                  isClickable
                    ? "cursor-pointer hover:bg-muted/50"
                    : "cursor-default opacity-50"
                )}
              >
                {isCompleted ? (
                  <Check
                    size={12}
                    className="text-green-600 shrink-0"
                    strokeWidth={3}
                  />
                ) : isCurrent ? (
                  <Circle
                    size={12}
                    className="text-accent fill-accent shrink-0"
                  />
                ) : (
                  <Circle size={12} className="text-border shrink-0" />
                )}

                <span
                  className={cn(
                    "leading-tight",
                    isCompleted && "text-muted-foreground",
                    isCurrent && "font-semibold text-foreground",
                    !isCompleted && !isCurrent && "text-muted-foreground"
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
