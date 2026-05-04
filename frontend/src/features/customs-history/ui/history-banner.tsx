"use client";

/**
 * HistoryBanner — Phase A Req 10, Task 11.
 *
 * Surfaces the most recent customs choice for the current
 * `(tnved_code, country)` combination so the specialist can re-apply it.
 *
 * Two visual modes:
 *   - Default (is_actual=true): blue tint, neutral text «Заполнено из истории
 *     от {date} ({email}). Проверьте актуальность.»
 *   - Warning (is_actual=false): amber tint, alternate text «Выбор от {date}
 *     ({email}) — Alta изменила варианты, проверьте применимость.»
 *
 * Pure component — parent owns the apply/dismiss state.
 */

import { Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";

import { formatDateRussian } from "../lib/format-date";
import type { HistoryMatch } from "../model/types";

export interface HistoryBannerProps {
  suggestion: HistoryMatch;
  onApply: () => void;
  onDismiss: () => void;
}

export function HistoryBanner({
  suggestion,
  onApply,
  onDismiss,
}: HistoryBannerProps) {
  const dateStr = formatDateRussian(suggestion.created_at);
  const userEmail = suggestion.user_email ?? "пользователем";
  const isActualWarning = !suggestion.is_actual;

  const cardClass = isActualWarning
    ? "border-amber-900 bg-amber-950/20"
    : "border-blue-900 bg-blue-950/20";

  const headerText = isActualWarning
    ? `Выбор от ${dateStr} (${userEmail}) — Alta изменила варианты, проверьте применимость`
    : `Заполнено из истории от ${dateStr} (${userEmail}). Проверьте актуальность.`;

  return (
    <div
      className={`flex items-center justify-between gap-2 rounded-md border ${cardClass} px-3 py-2 mb-3`}
      data-testid="customs-history-banner"
    >
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <Sparkles size={14} className="shrink-0 text-blue-400" />
        <div className="text-xs text-foreground/90 truncate">{headerText}</div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <Button
          size="sm"
          variant="outline"
          onClick={onApply}
          className="text-xs h-7"
        >
          Применить
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={onDismiss}
          className="h-7 w-7 p-0"
          aria-label="Скрыть подсказку"
        >
          <X size={14} />
        </Button>
      </div>
    </div>
  );
}
