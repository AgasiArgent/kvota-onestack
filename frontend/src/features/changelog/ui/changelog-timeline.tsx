"use client";

import { useEffect } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ChangelogEntry } from "@/entities/changelog/types";
import { markChangelogRead } from "@/entities/changelog/mutations";

const RUSSIAN_MONTHS: Record<number, string> = {
  1: "января",
  2: "февраля",
  3: "марта",
  4: "апреля",
  5: "мая",
  6: "июня",
  7: "июля",
  8: "августа",
  9: "сентября",
  10: "октября",
  11: "ноября",
  12: "декабря",
};

function formatDateRussian(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  const day = d.getDate();
  const month = RUSSIAN_MONTHS[d.getMonth() + 1] ?? "";
  const year = d.getFullYear();
  return `${day} ${month} ${year}`;
}

const CATEGORY_CONFIG: Record<
  string,
  { label: string; className: string }
> = {
  feature: {
    label: "Новое",
    className: "bg-accent-subtle text-accent",
  },
  fix: {
    label: "Исправление",
    className: "bg-success-bg text-success",
  },
  update: {
    label: "Обновление",
    className: "bg-sidebar text-text-muted",
  },
  improvement: {
    label: "Улучшение",
    className: "bg-warning-bg text-warning",
  },
};

interface ChangelogTimelineProps {
  entries: ChangelogEntry[];
}

export function ChangelogTimeline({ entries }: ChangelogTimelineProps) {
  useEffect(() => {
    markChangelogRead();
  }, []);

  if (entries.length === 0) {
    return (
      <p className="text-text-muted text-sm">
        Пока нет записей в журнале обновлений.
      </p>
    );
  }

  return (
    <div className="relative">
      {/* Vertical timeline line */}
      <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border-light" />

      <div className="space-y-8">
        {entries.map((entry) => {
          const category = CATEGORY_CONFIG[entry.category] ?? CATEGORY_CONFIG.update;

          return (
            <div key={entry.slug} className="relative flex gap-5">
              {/* Timeline dot */}
              <div className="relative z-10 mt-1.5 shrink-0">
                <div className="h-[15px] w-[15px] rounded-full border-2 border-border bg-card" />
              </div>

              {/* Content card */}
              <div className="flex-1 min-w-0 pb-2">
                {/* Date & version header */}
                <div className="flex items-center gap-2 mb-2">
                  {entry.version && (
                    <span className="text-xs font-semibold text-text-muted">
                      v{entry.version}
                    </span>
                  )}
                  {entry.version && (
                    <span className="text-text-subtle text-xs">—</span>
                  )}
                  <span className="text-xs text-text-muted">
                    {formatDateRussian(entry.date)}
                  </span>
                </div>

                {/* Category badge + title */}
                <div className="flex items-center gap-2 mb-3">
                  <Badge
                    className={cn(
                      "rounded-sm px-2.5 py-1 text-xs font-semibold border-0",
                      category.className
                    )}
                  >
                    {category.label}
                  </Badge>
                  <h3 className="text-base font-semibold text-text">
                    {entry.title}
                  </h3>
                </div>

                {/* Body content */}
                <div
                  className="changelog-body bg-card border border-border-light rounded-lg p-5"
                  dangerouslySetInnerHTML={{ __html: entry.body_html }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
