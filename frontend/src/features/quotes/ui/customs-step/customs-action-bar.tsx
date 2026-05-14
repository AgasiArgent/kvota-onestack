"use client";

import { Check, CheckCircle, Loader2, SkipForward } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { QuoteItemRow } from "@/entities/quote/queries";

function ext<T>(row: unknown): T {
  return row as T;
}

type ItemExtras = {
  hs_code?: string | null;
  customs_duty?: number | null;
  product_name?: string | null;
  product_code?: string | null;
};

interface CustomsActionBarProps {
  items: QuoteItemRow[];
  onCompleteCustoms: () => void;
  onSkipCustoms: () => void;
  completing?: boolean;
  skipping?: boolean;
  canSkipCustoms?: boolean;
  /**
   * Timestamp when customs was already marked complete for this quote.
   * Non-null means the server will reject another `complete_customs`
   * action with HTTP 422 «Customs already completed». We disable the
   * button up-front so the user never sees the silent-failure path
   * (Testing 2 row 11). Mirrors the per-quote gate enforced by
   * `services/workflow_service.complete_customs`.
   */
  customsCompletedAt?: string | null;
}

function itemDisplayName(extras: ItemExtras): string {
  const name = (extras.product_name || "").trim();
  const code = (extras.product_code || "").trim();
  if (name && code) return `${name} (${code})`;
  return name || code || "позиция без названия";
}

function findMissingHsCode(items: QuoteItemRow[]): string[] {
  const missing: string[] = [];
  for (const item of items) {
    const extras = ext<ItemExtras>(item);
    const hs = (extras.hs_code || "").trim();
    if (!hs) {
      missing.push(itemDisplayName(extras));
    }
  }
  return missing;
}

function formatDisabledReason(
  totalItems: number,
  missingNames: string[],
  completing: boolean,
  skipping: boolean,
  alreadyCompleted: boolean,
): string | null {
  // Already-completed gate takes precedence — the server rejects any
  // further `complete_customs` action with HTTP 422, and we want a
  // self-explanatory tooltip instead of a silent click (Testing 2 row 11).
  if (alreadyCompleted) return "Таможня по этому КП уже завершена.";
  if (completing) return "Завершение в процессе…";
  if (skipping) return "Пропуск в процессе…";
  if (totalItems === 0) {
    return "Нет позиций для расчёта таможни.";
  }
  if (missingNames.length === 0) return null;
  const lines = missingNames
    .slice(0, 5)
    .map((name) => `• ${name}: укажите ТН ВЭД`);
  if (missingNames.length > 5) {
    lines.push(`• …и ещё ${missingNames.length - 5}`);
  }
  return "Заполните перед завершением:\n" + lines.join("\n");
}

export function CustomsActionBar({
  items,
  onCompleteCustoms,
  onSkipCustoms,
  completing = false,
  skipping = false,
  canSkipCustoms = false,
  customsCompletedAt = null,
}: CustomsActionBarProps) {
  const totalItems = items.length;
  const itemsWithHsCode = items.filter((item) => {
    const extras = ext<ItemExtras>(item);
    return extras.hs_code && extras.hs_code.trim().length > 0;
  }).length;
  const itemsWithDuty = items.filter((item) => {
    const extras = ext<ItemExtras>(item);
    return extras.customs_duty != null;
  }).length;

  const alreadyCompleted = Boolean(customsCompletedAt);
  const allHaveHsCode = totalItems > 0 && itemsWithHsCode === totalItems;
  const completeDisabled =
    alreadyCompleted || !allHaveHsCode || completing || skipping;

  // Mirrors the LogisticsActionBar tooltip pattern (PR #120) — closes
  // probe finding #4 from the logistics-tab UX session: previously the
  // disabled "Таможня завершена" button gave no explanation of which
  // items were missing ТН ВЭД codes. Now the tooltip lists the first 5.
  // Testing 2 row 11 extends the same tooltip with the "already
  // completed" branch so the silent 422 path is replaced by a visible
  // disabled state.
  const missingNames = findMissingHsCode(items);
  const disabledReason = completeDisabled
    ? formatDisabledReason(
        totalItems,
        missingNames,
        completing,
        skipping,
        alreadyCompleted,
      )
    : null;

  const completeButton = (
    <Button
      size="sm"
      className="bg-success text-white hover:bg-success/90"
      disabled={completeDisabled}
      onClick={onCompleteCustoms}
      aria-label="Таможня завершена"
    >
      {completing ? (
        <Loader2 size={14} className="animate-spin" aria-hidden />
      ) : (
        <CheckCircle size={14} aria-hidden />
      )}
      Таможня завершена
    </Button>
  );

  // Testing 2 row 11 (part 2): once customs is complete on the server,
  // render a static badge instead of a disabled-but-green Button. The
  // disabled `bg-success` Button still reads as "active/clickable" to
  // testers — they click it, get a silent no-op, and report «горит, но
  // ничего не происходит». A Badge has no button affordance, so the
  // "done" state is visually unambiguous.
  const completedBadge = (
    <Badge
      variant="default"
      className="bg-green-100 text-green-700 px-3 py-1.5 h-auto inline-flex items-center gap-1.5"
      data-testid="customs-completed-badge"
    >
      <Check size={14} aria-hidden />
      <span>Таможня завершена</span>
    </Badge>
  );

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-3">
      {alreadyCompleted ? (
        completedBadge
      ) : disabledReason ? (
        <Tooltip>
          <TooltipTrigger render={<span className="inline-block" />}>
            {completeButton}
          </TooltipTrigger>
          <TooltipContent
            side="bottom"
            className="max-w-xs whitespace-pre-line text-xs"
          >
            {disabledReason}
          </TooltipContent>
        </Tooltip>
      ) : (
        completeButton
      )}

      {canSkipCustoms && (
        <Button
          variant="outline"
          size="sm"
          disabled={completing || skipping}
          onClick={onSkipCustoms}
        >
          {skipping ? (
            <Loader2 size={14} className="animate-spin" aria-hidden />
          ) : (
            <SkipForward size={14} aria-hidden />
          )}
          Пропустить таможню
        </Button>
      )}

      <span className="ml-auto text-sm text-muted-foreground tabular-nums">
        {itemsWithHsCode}/{totalItems} заполнено ТН ВЭД | {itemsWithDuty} с
        пошлиной
      </span>
    </div>
  );
}
