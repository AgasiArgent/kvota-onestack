"use client";

import { useState } from "react";
import { Calculator, FileDown, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { QuoteDetailRow } from "@/entities/quote/queries";

// Statuses where "Ответ клиента" dropdown should be visible
const CLIENT_RESPONSE_STATUSES = new Set([
  "approved",
  "sent_to_client",
]);

export type ClientResponseModal =
  | "accept"
  | "changes"
  | "decline"
  | "cancel"
  | null;

interface SalesActionBarProps {
  quote: QuoteDetailRow;
  onOpenModal?: (modal: ClientResponseModal) => void;
}

export function SalesActionBar({ quote, onOpenModal }: SalesActionBarProps) {
  const showClientResponse = CLIENT_RESPONSE_STATUSES.has(quote.workflow_status ?? "");

  function handleCalculate() {
    // Will be wired to POST /api/calculate in Phase 2
    console.log("Calculate triggered for quote:", quote.id);
  }

  function handleExportPdf() {
    // Will be wired to GET /api/export-pdf in Phase 2
    console.log("Export PDF triggered for quote:", quote.id);
  }

  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-2">
      <Button
        size="sm"
        className="bg-accent text-white hover:bg-accent-hover"
        onClick={handleCalculate}
      >
        <Calculator size={14} />
        Рассчитать
      </Button>

      <Button size="sm" variant="outline" onClick={handleExportPdf}>
        <FileDown size={14} />
        КП PDF
      </Button>

      {showClientResponse && (
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button size="sm" variant="outline">
                Ответ клиента
                <ChevronDown size={14} />
              </Button>
            }
          />
          <DropdownMenuContent align="start" sideOffset={4}>
            <DropdownMenuItem onClick={() => onOpenModal?.("accept")}>
              Клиент принимает
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onOpenModal?.("changes")}>
              Клиент просит изменения
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onOpenModal?.("decline")}>
              Клиент отказался
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              onClick={() => onOpenModal?.("cancel")}
            >
              Отменить КП
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}
