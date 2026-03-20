"use client";

import { Calculator, FileDown, ChevronDown, ArrowRight, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { QuoteDetailRow } from "@/entities/quote/queries";

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
  const status = quote.workflow_status ?? "draft";

  function handleSubmitToProcurement() {
    console.log("Submit to procurement:", quote.id);
  }

  function handleCalculate() {
    console.log("Calculate:", quote.id);
  }

  function handleExportPdf() {
    console.log("Export PDF:", quote.id);
  }

  function handleSendToClient() {
    console.log("Send to client:", quote.id);
  }

  // Workflow-aware action bar: only show relevant actions per status
  return (
    <div className="sticky top-[52px] z-[5] bg-card border-b border-border px-6 py-2 flex items-center gap-2">
      {/* Draft: only action is to submit to procurement */}
      {status === "draft" && (
        <Button
          size="sm"
          className="bg-accent text-white hover:bg-accent-hover"
          onClick={handleSubmitToProcurement}
        >
          <ArrowRight size={14} />
          Передать в закупки
        </Button>
      )}

      {/* Waiting for procurement — no actions, just info */}
      {status === "pending_procurement" && (
        <span className="text-sm text-muted-foreground py-1">
          Ожидание закупки...
        </span>
      )}

      {/* Procurement complete — can calculate */}
      {status === "procurement_complete" && (
        <Button
          size="sm"
          className="bg-accent text-white hover:bg-accent-hover"
          onClick={handleCalculate}
        >
          <Calculator size={14} />
          Рассчитать
        </Button>
      )}

      {/* Calculated — can export PDF and send to client */}
      {status === "calculated" && (
        <>
          <Button size="sm" variant="outline" onClick={handleExportPdf}>
            <FileDown size={14} />
            Скачать PDF
          </Button>
          <Button
            size="sm"
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleSendToClient}
          >
            <Send size={14} />
            Отправить клиенту
          </Button>
        </>
      )}

      {/* Sent to client / Approved — client response actions */}
      {(status === "sent_to_client" || status === "approved") && (
        <>
          <Button size="sm" variant="outline" onClick={handleExportPdf}>
            <FileDown size={14} />
            Скачать PDF
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button size="sm" className="bg-accent text-white hover:bg-accent-hover">
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
        </>
      )}
    </div>
  );
}
