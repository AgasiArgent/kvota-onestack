"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Paperclip, Wallet, Ban, Loader2, Info } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { cancelQuote } from "@/entities/quote/mutations";
import type { QuoteDetailRow } from "@/entities/quote/queries";
import type { QuoteStep } from "@/entities/quote/types";
// Direct import from the source module, NOT the barrel — the barrel re-exports
// queries.ts which transitively pulls `next/headers` from supabase/server.ts.
// Pulling that into a Client Component (this file) breaks the Turbopack build.
import { STATUS_LABELS, STATUS_BADGE_STYLES } from "@/entities/quote/status-labels";
import { DeleteMenu } from "./delete-menu/delete-menu";

const PLAN_FACT_ROLES = ["finance", "admin", "top_manager"];
const CANCEL_ROLES = ["sales", "head_of_sales", "admin"];
const TERMINAL_STATUSES = new Set(["cancelled", "rejected", "spec_signed", "deal"]);

interface QuoteStickyHeaderProps {
  quote: QuoteDetailRow;
  documentCount?: number;
  activeStep?: QuoteStep;
  userRoles?: string[];
  isContextOpen: boolean;
  onToggleContext: () => void;
}

export function QuoteStickyHeader({
  quote,
  documentCount,
  activeStep,
  userRoles = [],
  isContextOpen,
  onToggleContext,
}: QuoteStickyHeaderProps) {
  const [cancelOpen, setCancelOpen] = useState(false);
  const isDocumentsActive = activeStep === "documents";
  const isPlanFactActive = activeStep === "plan-fact";
  const showPlanFact = userRoles.some((r) => PLAN_FACT_ROLES.includes(r));
  const workflowStatus = quote.workflow_status ?? "draft";
  const statusStyle =
    STATUS_BADGE_STYLES[workflowStatus] ?? "bg-slate-100 text-slate-700";
  const statusLabel = STATUS_LABELS[workflowStatus] ?? workflowStatus;

  // Pin timezone to avoid React hydration mismatch (#418) — server (UTC) and
  // client (user tz) would otherwise round created_at to different calendar days.
  const createdAtLabel = quote.created_at
    ? new Date(quote.created_at).toLocaleDateString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        timeZone: "Europe/Moscow",
      })
    : null;

  const totalAmount = quote.total_amount_quote ?? null;
  const formattedAmount =
    totalAmount != null
      ? new Intl.NumberFormat("ru-RU", {
          minimumFractionDigits: 0,
          maximumFractionDigits: 2,
        }).format(totalAmount)
      : null;

  const profit = quote.profit_quote_currency ?? null;
  const revenue = quote.revenue_no_vat_quote_currency ?? null;
  const marginPercent =
    profit != null && revenue != null && revenue !== 0
      ? (profit / revenue) * 100
      : null;
  const marginDisplay =
    marginPercent != null ? `${marginPercent.toFixed(1)}%` : null;

  const currency = quote.currency ?? "";

  return (
    <>
      <div className="sticky top-0 z-10 bg-card border-b border-border px-6 py-3">
        <div className="flex items-center justify-between gap-4">
          {/* Left: navigation + identification */}
          <div className="flex items-center gap-3 min-w-0">
            <Link
              href="/quotes"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground shrink-0"
            >
              <ArrowLeft size={16} />
              КП
            </Link>

            <span className="font-mono text-sm font-medium shrink-0">
              {quote.idn_quote}
            </span>

            <Badge className={cn("shrink-0 border-0", statusStyle)}>
              {statusLabel}
            </Badge>

            {createdAtLabel && (
              <span className="text-xs text-muted-foreground shrink-0 tabular-nums">
                от {createdAtLabel}
              </span>
            )}

            {quote.customer && (
              <Link
                href={`/customers/${quote.customer.id}`}
                className="text-sm text-muted-foreground hover:text-accent truncate"
              >
                {quote.customer.name}
              </Link>
            )}
          </div>

          {/* Right: cancel + plan-fact + documents + amount + margin */}
          <div className="flex items-center gap-4 shrink-0">
            {userRoles.some((r) => CANCEL_ROLES.includes(r)) &&
              !TERMINAL_STATUSES.has(workflowStatus) && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground hover:text-destructive"
                  onClick={() => setCancelOpen(true)}
                >
                  <Ban size={14} />
                  Отменить
                </Button>
              )}

            <button
              onClick={onToggleContext}
              className={cn(
                "relative inline-flex items-center gap-1 text-sm transition-colors rounded-md px-2 py-1",
                isContextOpen
                  ? "text-foreground bg-muted"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
              aria-label={isContextOpen ? "Свернуть контекст" : "Развернуть контекст"}
            >
              <Info size={16} />
            </button>

            {showPlanFact && (
              <Link
                href={
                  isPlanFactActive
                    ? `/quotes/${quote.id}`
                    : `/quotes/${quote.id}?step=plan-fact`
                }
                className={cn(
                  "relative inline-flex items-center gap-1 text-sm transition-colors rounded-md px-2 py-1",
                  isPlanFactActive
                    ? "text-foreground bg-muted"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                )}
                aria-pressed={isPlanFactActive}
                title={isPlanFactActive ? "Закрыть план-факт" : "Открыть план-факт"}
              >
                <Wallet size={16} />
              </Link>
            )}

            <Link
              href={
                isDocumentsActive
                  ? `/quotes/${quote.id}`
                  : `/quotes/${quote.id}?step=documents`
              }
              className={cn(
                "relative inline-flex items-center gap-1 text-sm transition-colors rounded-md px-2 py-1",
                isDocumentsActive
                  ? "text-foreground bg-muted"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
              aria-pressed={isDocumentsActive}
              title={isDocumentsActive ? "Закрыть документы" : "Открыть документы"}
            >
              <Paperclip size={16} />
              {documentCount != null && documentCount > 0 && (
                <Badge
                  variant="secondary"
                  className="h-5 min-w-5 px-1 text-[10px] font-semibold leading-none"
                >
                  {documentCount}
                </Badge>
              )}
            </Link>

            {formattedAmount && (
              <span className="text-sm font-medium">
                {formattedAmount}{" "}
                <span className="text-muted-foreground">{currency}</span>
              </span>
            )}

            {marginDisplay && (
              <span className="text-sm text-muted-foreground">
                Маржа {marginDisplay}
              </span>
            )}

            <DeleteMenu
              quoteId={quote.id}
              entityName={quote.idn_quote}
              roles={userRoles}
            />
          </div>
        </div>

        {/* Cancellation info banner */}
        {workflowStatus === "cancelled" && quote.cancellation_comment && (
          <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-800">
            <span className="font-medium">Причина отмены:</span>{" "}
            {quote.cancellation_comment}
          </div>
        )}
      </div>

      <CancelQuoteDialog
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        quoteId={quote.id}
        idnQuote={quote.idn_quote}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Cancel dialog (embedded in header for global access)
// ---------------------------------------------------------------------------

function CancelQuoteDialog({
  open,
  onClose,
  quoteId,
  idnQuote,
}: {
  open: boolean;
  onClose: () => void;
  quoteId: string;
  idnQuote: string;
}) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    if (!reason.trim()) return;
    setSubmitting(true);
    try {
      await cancelQuote(quoteId, reason.trim());
      toast.success("КП отменена");
      setReason("");
      onClose();
      router.refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось отменить КП"
      );
    } finally {
      setSubmitting(false);
    }
  }

  function handleClose() {
    setReason("");
    onClose();
  }

  return (
    <Dialog open={open} onOpenChange={(val) => !val && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Отменить заявку</DialogTitle>
          <DialogDescription>
            КП {idnQuote} будет отменена. Это действие необратимо.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-1.5">
          <label className="text-sm font-medium">
            Причина отмены <span className="text-destructive">*</span>
          </label>
          <Textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Укажите причину отмены КП"
            rows={3}
          />
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={submitting}>
            Назад
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={!reason.trim() || submitting}
          >
            {submitting && <Loader2 size={14} className="animate-spin" />}
            Отменить КП
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
