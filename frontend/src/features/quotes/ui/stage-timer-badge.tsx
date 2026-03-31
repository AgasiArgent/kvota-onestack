"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

export type TimerStatus = "ok" | "warning" | "overdue" | "no_timer" | "no_deadline";

interface StageTimerBadgeProps {
  stageEnteredAt: string;
  deadlineHours: number | null;
  overrideHours: number | null;
  status: TimerStatus;
}

function computeElapsed(stageEnteredAt: string): number {
  const entered = new Date(stageEnteredAt).getTime();
  const now = Date.now();
  return Math.max(0, now - entered);
}

function formatElapsed(ms: number): string {
  const totalMinutes = Math.floor(ms / 60_000);
  const totalHours = Math.floor(totalMinutes / 60);
  const totalDays = Math.floor(totalHours / 24);

  if (totalMinutes < 60) {
    return `${totalMinutes}м`;
  }

  if (totalHours < 24) {
    const remainingMinutes = totalMinutes % 60;
    return `${totalHours}ч ${remainingMinutes}м`;
  }

  const remainingHours = totalHours % 24;
  return `${totalDays}д ${remainingHours}ч`;
}

function computeStatus(
  elapsedMs: number,
  deadlineHours: number | null,
  overrideHours: number | null
): TimerStatus {
  const effectiveDeadline = overrideHours ?? deadlineHours;
  if (effectiveDeadline === null) return "no_deadline";

  const elapsedHours = elapsedMs / 3_600_000;
  if (elapsedHours >= effectiveDeadline) return "overdue";
  if (elapsedHours >= effectiveDeadline * 0.8) return "warning";
  return "ok";
}

const STATUS_STYLES: Record<TimerStatus, string> = {
  ok: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  warning: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  overdue: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  no_timer: "",
  no_deadline: "bg-muted text-muted-foreground",
};

export function StageTimerBadge({
  stageEnteredAt,
  deadlineHours,
  overrideHours,
  status: initialStatus,
}: StageTimerBadgeProps) {
  const [elapsedMs, setElapsedMs] = useState(() =>
    computeElapsed(stageEnteredAt)
  );

  useEffect(() => {
    setElapsedMs(computeElapsed(stageEnteredAt));

    const interval = setInterval(() => {
      setElapsedMs(computeElapsed(stageEnteredAt));
    }, 60_000);

    return () => clearInterval(interval);
  }, [stageEnteredAt]);

  if (initialStatus === "no_timer") return null;

  const liveStatus = computeStatus(elapsedMs, deadlineHours, overrideHours);
  const displayStatus = initialStatus === "no_deadline" ? "no_deadline" : liveStatus;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-1.5 py-0.5 text-[9px] font-medium leading-none whitespace-nowrap",
        STATUS_STYLES[displayStatus]
      )}
      title={
        displayStatus === "no_deadline"
          ? "Норматив не задан"
          : `${formatElapsed(elapsedMs)} из ${overrideHours ?? deadlineHours}ч`
      }
    >
      {formatElapsed(elapsedMs)}
    </span>
  );
}
