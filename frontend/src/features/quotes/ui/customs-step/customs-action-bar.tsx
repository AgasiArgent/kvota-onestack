"use client";

import { CheckCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { QuoteItemRow } from "@/entities/quote/queries";

function ext<T>(row: unknown): T {
  return row as T;
}

type ItemExtras = {
  hs_code?: string | null;
  customs_duty?: number | null;
};

interface CustomsActionBarProps {
  items: QuoteItemRow[];
  onCompleteCustoms: () => void;
  completing?: boolean;
}

export function CustomsActionBar({
  items,
  onCompleteCustoms,
  completing = false,
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

  const allHaveHsCode = totalItems > 0 && itemsWithHsCode === totalItems;

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-3">
      <Button
        size="sm"
        className="bg-success text-white hover:bg-success/90"
        disabled={!allHaveHsCode || completing}
        onClick={onCompleteCustoms}
      >
        {completing ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <CheckCircle size={14} />
        )}
        Таможня завершена
      </Button>

      <span className="ml-auto text-sm text-muted-foreground tabular-nums">
        {itemsWithHsCode}/{totalItems} заполнено ТН ВЭД | {itemsWithDuty} с
        пошлиной
      </span>
    </div>
  );
}
