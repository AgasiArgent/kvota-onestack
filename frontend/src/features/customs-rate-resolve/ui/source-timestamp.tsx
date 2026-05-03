"use client";

import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";

export interface SourceTimestampProps {
  /** ISO-8601 timestamp from `/resolve-rates` response. */
  fetchedAt: string | null;
  /** When provided, renders a Refresh button that triggers force-live re-fetch. */
  onRefresh?: () => void;
  /** Disables the refresh button while a request is in flight. */
  refreshing?: boolean;
}

/**
 * Humanize a UTC ISO timestamp into a "N минут назад" string.
 *
 * Pure for unit testing — no side effects, no Date.now coupling outside the
 * caller's `now` parameter.
 */
export function humanizeAge(
  isoTimestamp: string,
  now: Date = new Date()
): string {
  const then = new Date(isoTimestamp);
  if (Number.isNaN(then.getTime())) return "неизвестно";

  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.max(0, Math.floor(diffMs / 1000));

  if (diffSec < 60) return "только что";

  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} мин. назад`;

  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH} ч. назад`;

  const diffDay = Math.floor(diffH / 24);
  if (diffDay < 30) return `${diffDay} дн. назад`;

  // Older than 30 days — show absolute date instead.
  return then.toLocaleDateString("ru-RU", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function SourceTimestamp({
  fetchedAt,
  onRefresh,
  refreshing = false,
}: SourceTimestampProps) {
  return (
    <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
      <span>
        {fetchedAt
          ? `Обновлено ${humanizeAge(fetchedAt)}`
          : "Время обновления неизвестно"}
      </span>
      {onRefresh && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onRefresh}
          disabled={refreshing}
          className="h-7 gap-1.5 px-2 text-xs"
        >
          <RefreshCw
            size={12}
            className={refreshing ? "animate-spin" : undefined}
          />
          Обновить
        </Button>
      )}
    </div>
  );
}
