import type { LucideIcon } from "lucide-react";
import { Briefcase, AlertTriangle, CheckCircle2, Clock4 } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * WorkspaceStatsStrip — 4-card KPI overview for head-of-* on workspace pages.
 *
 * Cards:
 *   1. В работе        — count of active invoices assigned to team
 *   2. Просрочено       — count past deadline
 *   3. На этой неделе   — completed this calendar week
 *   4. Средний SLA      — avg hours-to-completion over last 30d
 *
 * Color treatment: semantic tokens only. Never hex.
 */

interface StatCardData {
  key: "active" | "overdue" | "weekDone" | "avgSla";
  label: string;
  value: string | number;
  delta?: string;
  tone: "neutral" | "error" | "success" | "warning";
}

interface WorkspaceStatsStripProps {
  domain: "logistics" | "customs";
  stats: {
    active: number;
    overdue: number;
    completedThisWeek: number;
    avgSlaHours: number;
    deltaActive?: string;
    deltaOverdue?: string;
    deltaWeekDone?: string;
    deltaAvgSla?: string;
  };
}

const ICONS: Record<StatCardData["key"], LucideIcon> = {
  active: Briefcase,
  overdue: AlertTriangle,
  weekDone: CheckCircle2,
  avgSla: Clock4,
};

const TONE_CLS: Record<StatCardData["tone"], { icon: string; value: string }> = {
  neutral: { icon: "text-text-muted", value: "text-text" },
  error: { icon: "text-error", value: "text-error" },
  success: { icon: "text-success", value: "text-text" },
  warning: { icon: "text-warning", value: "text-text" },
};

export function WorkspaceStatsStrip({ domain, stats }: WorkspaceStatsStripProps) {
  const cards: StatCardData[] = [
    {
      key: "active",
      label: domain === "logistics" ? "В работе у логистов" : "В работе у таможни",
      value: stats.active,
      delta: stats.deltaActive,
      tone: "neutral",
    },
    {
      key: "overdue",
      label: "Просрочено",
      value: stats.overdue,
      delta: stats.deltaOverdue,
      tone: stats.overdue > 0 ? "error" : "neutral",
    },
    {
      key: "weekDone",
      label: "Завершено на этой неделе",
      value: stats.completedThisWeek,
      delta: stats.deltaWeekDone,
      tone: "success",
    },
    {
      key: "avgSla",
      label: "Средний SLA",
      value: `${stats.avgSlaHours.toFixed(1)} ч`,
      delta: stats.deltaAvgSla,
      tone: "neutral",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
      {cards.map((card) => {
        const Icon = ICONS[card.key];
        const tone = TONE_CLS[card.tone];
        return (
          <div
            key={card.key}
            className="rounded-lg border border-border-light bg-card p-4"
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon size={14} strokeWidth={2} className={tone.icon} aria-hidden />
              <span className="text-xs text-text-muted">{card.label}</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span
                className={cn(
                  "text-2xl font-semibold tabular-nums tracking-tight",
                  tone.value,
                )}
              >
                {card.value}
              </span>
              {card.delta && (
                <span className="text-xs text-text-subtle tabular-nums">
                  {card.delta}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
