"use client";

import { useRouter } from "next/navigation";
import { Check, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QuoteStep } from "@/entities/quote/types";
import type { StageDeadlineData } from "@/entities/quote/queries";
import { StageTimerBadge, type TimerStatus } from "./stage-timer-badge";
import { DeadlineOverride } from "./deadline-override";

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
    statuses: ["pending_logistics", "pending_logistics_and_customs"],
  },
  {
    key: "customs",
    label: "Таможня",
    statuses: ["pending_customs", "pending_logistics_and_customs"],
  },
  {
    key: "calculation",
    label: "Расчёт",
    statuses: ["procurement_complete", "calculated", "pending_sales_review"],
  },
  {
    key: "control",
    label: "Контроль",
    statuses: ["pending_quote_control", "pending_approval"],
  },
  {
    key: "negotiation",
    label: "Переговоры",
    statuses: ["sent_to_client", "approved", "accepted"],
  },
  {
    key: "specification",
    label: "Спецификация",
    statuses: ["pending_spec_control", "spec_draft", "spec_signed"],
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const SPEC_STATUS_BADGES: Record<string, { label: string; className: string }> = {
  pending_spec_control: { label: "Черновик", className: "bg-amber-100 text-amber-700" },
  spec_draft: { label: "Черновик", className: "bg-amber-100 text-amber-700" },
  spec_signed: { label: "Подписана", className: "bg-green-100 text-green-700" },
};

const TERMINAL_STATUSES = new Set(["draft", "deal", "rejected", "cancelled"]);

function getTimerStatus(
  stageDeadline: StageDeadlineData,
  workflowStatus: string
): TimerStatus {
  if (TERMINAL_STATUSES.has(workflowStatus)) return "no_timer";
  if (!stageDeadline.stageEnteredAt) return "no_timer";
  if (stageDeadline.deadlineHours === null && stageDeadline.overrideHours === null) {
    return "no_deadline";
  }

  const effectiveDeadline = stageDeadline.overrideHours ?? stageDeadline.deadlineHours;
  if (effectiveDeadline === null) return "no_deadline";

  const elapsedMs = Date.now() - new Date(stageDeadline.stageEnteredAt).getTime();
  const elapsedHours = elapsedMs / 3_600_000;

  if (elapsedHours >= effectiveDeadline) return "overdue";
  if (elapsedHours >= effectiveDeadline * 0.8) return "warning";
  return "ok";
}

interface QuoteStatusRailProps {
  activeStep: QuoteStep;
  currentWorkflowStep: QuoteStep;
  allowedSteps: QuoteStep[];
  isAdmin: boolean;
  quoteId: string;
  workflowStatus: string;
  stageDeadline: StageDeadlineData;
}

export function QuoteStatusRail({
  activeStep,
  allowedSteps,
  isAdmin,
  quoteId,
  workflowStatus,
  stageDeadline,
}: QuoteStatusRailProps) {
  const router = useRouter();

  // Find which step index the current workflow status maps to
  const currentStepIdx = STEPS.findIndex((s) =>
    s.statuses.includes(workflowStatus)
  );

  const timerStatus = getTimerStatus(stageDeadline, workflowStatus);

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
          const isCurrent = step.statuses.includes(workflowStatus);
          const isCompleted = currentStepIdx >= 0 && idx < currentStepIdx && !isCurrent;
          const isActive = step.key === activeStep;
          const isClickable = isAdmin || allowedSteps.includes(step.key);

          return (
            <li key={`${step.key}-${idx}`} className="group/step">
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
                  {step.key === "specification" && isCurrent && SPEC_STATUS_BADGES[workflowStatus] && (
                    <span className={cn(
                      "ml-1 inline-block text-[9px] px-1 py-0.5 rounded font-medium leading-none",
                      SPEC_STATUS_BADGES[workflowStatus].className
                    )}>
                      {SPEC_STATUS_BADGES[workflowStatus].label}
                    </span>
                  )}
                </span>
              </button>
              {isCurrent && timerStatus !== "no_timer" && stageDeadline.stageEnteredAt && (
                <div className="flex items-center gap-0.5 pl-[26px] pb-1">
                  <StageTimerBadge
                    stageEnteredAt={stageDeadline.stageEnteredAt}
                    deadlineHours={stageDeadline.deadlineHours}
                    overrideHours={stageDeadline.overrideHours}
                    status={timerStatus}
                  />
                  {isAdmin && (
                    <DeadlineOverride
                      quoteId={quoteId}
                      currentOverrideHours={stageDeadline.overrideHours}
                      globalDeadlineHours={stageDeadline.deadlineHours}
                    />
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
