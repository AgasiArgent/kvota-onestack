"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Calculator,
  FileDown,
  ChevronDown,
  ArrowRight,
  Send,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { config } from "@/shared/config";
import {
  submitToProcurement,
  sendToClient,
} from "@/entities/quote/mutations";
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
  const router = useRouter();
  const status = quote.workflow_status ?? "draft";
  const [loading, setLoading] = useState<string | null>(null);

  async function handleSubmitToProcurement() {
    setLoading("submit");
    try {
      await submitToProcurement(quote.id);
      toast.success("КП передана в закупки");
      router.refresh();
    } catch {
      toast.error("Не удалось передать в закупки");
    } finally {
      setLoading(null);
    }
  }

  async function handleCalculate() {
    setLoading("calculate");
    try {
      const res = await fetch(
        `${config.legacyAppUrl}/api/quotes/${quote.id}/calculate`,
        { method: "POST", credentials: "include" }
      );
      if (!res.ok) {
        throw new Error(`Failed: ${res.status}`);
      }
      toast.success("Расчёт выполнен");
      router.refresh();
    } catch {
      toast.error("Не удалось выполнить расчёт");
    } finally {
      setLoading(null);
    }
  }

  function handleExportPdf() {
    window.open(`/quotes/${quote.id}/export-kp`, "_blank");
  }

  async function handleSendToClient() {
    setLoading("send");
    try {
      await sendToClient(quote.id);
      toast.success("КП отправлено клиенту");
      router.refresh();
    } catch {
      toast.error("Не удалось отправить КП клиенту");
    } finally {
      setLoading(null);
    }
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
          disabled={loading === "submit"}
        >
          {loading === "submit" ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <ArrowRight size={14} />
          )}
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
          disabled={loading === "calculate"}
        >
          {loading === "calculate" ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Calculator size={14} />
          )}
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
            disabled={loading === "send"}
          >
            {loading === "send" ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Send size={14} />
            )}
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
