"use client";

import { useEffect, useState } from "react";
import { Clock, CheckCircle2, AlertTriangle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * SlaTimerBadge — visual SLA countdown for workspace queues.
 *
 * States:
 *   - completed (completedAt set)           → neutral gray + check icon
 *   - overdue   (now > deadlineAt)          → --error tones
 *   - warning   (< 24h left)                → --warning tones
 *   - on-track  (>= 24h left)               → --success tones
 *
 * Self-updating: re-renders every 60s via a cheap `Date.now()` tick.
 * `<time dateTime=...>` + tooltip with absolute deadline for assistive tech.
 *
 * Data source: invoices.{logistics,customs}_{assigned_at,deadline_at,completed_at}.
 */

interface SlaTimerBadgeProps {
  assignedAt: string | Date;
  deadlineAt: string | Date;
  completedAt?: string | Date | null;
  /** `sm` for table rows, `md` for standalone usage. */
  size?: "sm" | "md";
  className?: string;
}

type TimerState = "completed" | "overdue" | "warning" | "on-track";

function resolveState(
  now: number,
  deadline: number,
  completedAt?: string | Date | null,
): TimerState {
  if (completedAt) return "completed";
  const msLeft = deadline - now;
  if (msLeft <= 0) return "overdue";
  if (msLeft <= 24 * 60 * 60 * 1000) return "warning";
  return "on-track";
}

function formatRelative(msLeft: number): string {
  const absMs = Math.abs(msLeft);
  const minutes = Math.floor(absMs / 60_000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  const sign = msLeft < 0 ? "просрочено" : "осталось";
  if (days >= 1) return `${sign} ${days} ${pluralDays(days)}`;
  if (hours >= 1) return `${sign} ${hours} ${pluralHours(hours)}`;
  return `${sign} ${minutes} ${pluralMinutes(minutes)}`;
}

function pluralDays(n: number) {
  const mod100 = n % 100;
  const mod10 = n % 10;
  if (mod100 >= 11 && mod100 <= 14) return "дней";
  if (mod10 === 1) return "день";
  if (mod10 >= 2 && mod10 <= 4) return "дня";
  return "дней";
}
function pluralHours(n: number) {
  const mod100 = n % 100;
  const mod10 = n % 10;
  if (mod100 >= 11 && mod100 <= 14) return "часов";
  if (mod10 === 1) return "час";
  if (mod10 >= 2 && mod10 <= 4) return "часа";
  return "часов";
}
function pluralMinutes(n: number) {
  const mod100 = n % 100;
  const mod10 = n % 10;
  if (mod100 >= 11 && mod100 <= 14) return "минут";
  if (mod10 === 1) return "минута";
  if (mod10 >= 2 && mod10 <= 4) return "минуты";
  return "минут";
}

export function SlaTimerBadge({
  assignedAt,
  deadlineAt,
  completedAt,
  size = "sm",
  className,
}: SlaTimerBadgeProps) {
  const deadlineMs = new Date(deadlineAt).getTime();
  const [now, setNow] = useState<number>(() => Date.now());

  // Guard: invalid or missing deadline — render placeholder, no timer.
  if (!deadlineAt || Number.isNaN(deadlineMs)) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-sm border border-border-light px-2 py-0.5 text-xs text-text-subtle",
          className,
        )}
        title="Дедлайн не установлен"
      >
        <Clock size={12} strokeWidth={2} aria-hidden />
        —
      </span>
    );
  }

  useEffect(() => {
    if (completedAt) return;
    const tick = () => setNow(Date.now());
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, [completedAt]);

  const state = resolveState(now, deadlineMs, completedAt);
  const msLeft = deadlineMs - now;

  const Icon = state === "completed" ? CheckCircle2 : state === "overdue" ? AlertTriangle : Clock;
  const label =
    state === "completed"
      ? "Завершено"
      : formatRelative(msLeft);

  const paddingCls = size === "md" ? "px-2.5 py-1" : "px-2 py-0.5";
  const textCls = size === "md" ? "text-xs" : "text-xs";
  const iconSize = size === "md" ? 14 : 12;

  const stateCls: Record<TimerState, string> = {
    completed: "bg-sidebar text-text-muted border-border-light",
    overdue: "bg-error-bg text-error border-error/30",
    warning: "bg-warning-bg text-warning border-warning/30",
    "on-track": "bg-success-bg text-success border-success/30",
  };

  const absoluteDeadline = new Date(deadlineAt).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
  const absoluteAssigned = new Date(assignedAt).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <time
            dateTime={new Date(deadlineAt).toISOString()}
            className={cn(
              "inline-flex items-center gap-1 rounded-sm border font-medium tabular-nums transition-colors",
              paddingCls,
              textCls,
              stateCls[state],
              className,
            )}
          />
        }
      >
        <Icon size={iconSize} strokeWidth={2} aria-hidden />
        <span>{label}</span>
      </TooltipTrigger>
      <TooltipContent side="top" className="text-xs">
        <div className="space-y-0.5">
          <div>Дедлайн: {absoluteDeadline}</div>
          <div className="text-text-subtle">Назначено: {absoluteAssigned}</div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
