"use client";

import { useState } from "react";
import { ChevronRight, Upload } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { QuoteDetailRow } from "@/entities/quote/queries";

const DEAL_TYPE_LABELS: Record<string, string> = {
  price_check: "Проценка",
  tender: "Тендер",
  direct_request: "Прямой запрос",
};

interface SalesCollapsibleProps {
  quote: QuoteDetailRow;
}

export function SalesCollapsible({ quote }: SalesCollapsibleProps) {
  const [open, setOpen] = useState(false);

  const dealTypeLabel = quote.deal_type
    ? DEAL_TYPE_LABELS[quote.deal_type] ?? quote.deal_type
    : null;

  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="w-full flex items-center gap-2 px-5 py-3 text-sm font-medium hover:bg-muted/50 rounded-t-[var(--radius-lg)] transition-colors"
      >
        <ChevronRight
          size={16}
          className={cn(
            "text-muted-foreground transition-transform duration-200",
            open && "rotate-90"
          )}
        />
        Информация от отдела продаж
      </button>

      {open && (
        <CardContent className="px-5 pb-4 pt-0 space-y-4">
          {/* Deal type */}
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Тип запроса</label>
            {dealTypeLabel ? (
              <p className="text-sm font-medium">{dealTypeLabel}</p>
            ) : (
              <p className="text-sm text-muted-foreground">Не указан</p>
            )}
          </div>

          {/* Additional info */}
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Доп. информация</label>
            {quote.additional_info ? (
              <p className="text-sm whitespace-pre-wrap">{quote.additional_info}</p>
            ) : (
              <p className="text-sm text-muted-foreground">Не указана</p>
            )}
          </div>

          {/* Files placeholder */}
          <div className="space-y-1.5">
            <label className="text-xs text-muted-foreground">Файлы</label>
            <div className="flex items-center gap-2 py-3 px-4 border border-dashed border-border rounded-lg text-sm text-muted-foreground">
              <Upload size={16} />
              Загрузка файлов будет доступна позже
            </div>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
