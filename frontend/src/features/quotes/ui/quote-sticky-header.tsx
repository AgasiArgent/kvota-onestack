"use client";

import { useCallback, useState } from "react";
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
import { canViewQuoteFinancials } from "@/shared/lib/roles";
import { DeleteMenu } from "./delete-menu/delete-menu";

const PLAN_FACT_ROLES = ["finance", "admin", "top_manager"];
const CANCEL_ROLES = ["sales", "head_of_sales", "admin"];
const TERMINAL_STATUSES = new Set(["cancelled", "rejected", "spec_signed", "deal"]);

interface QuoteStickyHeaderProps {
  quote: QuoteDetailRow;
  documentCount?: number;
  activeStep?: QuoteStep;
  /**
   * Workflow-status-aware default step for the quote (e.g. «Закупки» for
   * pending_procurement). Used to build "close" links so toggling off
   * documents/plan-fact returns the user to the step matching the quote's
   * current stage instead of always landing on «Заявка». Falls back to
   * "sales" when not provided (legacy callers).
   */
  defaultStep?: QuoteStep;
  /**
   * Step the user came from before opening a side-panel step (documents /
   * plan-fact). Sourced from `?from=...` in the page URL by the parent.
   * When the user closes documents, we navigate back to this step instead
   * of the workflow-derived `defaultStep` — that way clicking the paperclip
   * from "Закупки" returns the user to "Закупки" on close, not "Заявка"
   * (МОП fail QP5).
   */
  fromStep?: QuoteStep | null;
  userRoles?: string[];
  isContextOpen: boolean;
  onToggleContext: () => void;
}

export function QuoteStickyHeader({
  quote,
  documentCount,
  activeStep,
  defaultStep = "sales",
  fromStep = null,
  userRoles = [],
  isContextOpen,
  onToggleContext,
}: QuoteStickyHeaderProps) {
  const router = useRouter();
  const [cancelOpen, setCancelOpen] = useState(false);

  // Back arrow returns to the previous browser page when there is history
  // (e.g. opened from /tasks or /workspace), and falls back to /quotes when
  // the user landed here directly (e.g. via a bookmark or paste-in URL).
  // FB-260513-155446-efa0: testers expected "Назад" to mean "previous page",
  // not "always the КП list".
  const handleBack = useCallback(() => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
    } else {
      router.push("/quotes");
    }
  }, [router]);
  const isDocumentsActive = activeStep === "documents";
  const isPlanFactActive = activeStep === "plan-fact";
  // The step we should return to when the user closes documents/plan-fact.
  // Priority:
  //   1. If we're currently NOT inside a side panel, the active step is the
  //      origin — record it as `from=` when opening a panel.
  //   2. If we're already inside the panel (re-render after navigate or
  //      page refresh), use the URL's `from` propagated via props.
  //   3. Fall back to the workflow-derived defaultStep.
  const currentNonPanelStep =
    activeStep && activeStep !== "documents" && activeStep !== "plan-fact"
      ? activeStep
      : null;
  const closeStep: QuoteStep =
    currentNonPanelStep ?? fromStep ?? defaultStep;
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

  // `kvota.quotes` carries two duplicate columns for the same idea — the
  // legacy `total_amount_quote` (never written) and `total_quote_currency`
  // (written by calculate_quote). Fall back so the header doesn't show «—»
  // while the calc-engine row has a valid total. Schema cleanup is a
  // separate concern.
  const totalAmount =
    quote.total_amount_quote ?? quote.total_quote_currency ?? null;
  const formattedAmount =
    totalAmount != null
      ? new Intl.NumberFormat("ru-RU", {
          minimumFractionDigits: 0,
          maximumFractionDigits: 2,
        }).format(totalAmount)
      : null;

  // Margin is hidden for procurement / logistics / customs roles (МОЗ-60).
  const showFinancials = canViewQuoteFinancials(userRoles);
  const profit = quote.profit_quote_currency ?? null;
  const revenue = quote.revenue_no_vat_quote_currency ?? null;
  const marginPercent =
    profit != null && revenue != null && revenue !== 0
      ? (profit / revenue) * 100
      : null;
  const marginDisplay =
    showFinancials && marginPercent != null
      ? `${marginPercent.toFixed(1)}%`
      : null;

  const currency = quote.currency ?? "";

  return (
    <>
      <div className="sticky top-0 z-10 bg-card border-b border-border px-6 py-3">
        <div className="flex items-center justify-between gap-4">
          {/* Left: navigation + identification */}
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={handleBack}
              className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground shrink-0"
            >
              <ArrowLeft size={16} />
              Назад
            </button>

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
                    ? `/quotes/${quote.id}?step=${closeStep}`
                    : `/quotes/${quote.id}?step=plan-fact${
                        currentNonPanelStep ? `&from=${currentNonPanelStep}` : ""
                      }`
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
                  ? `/quotes/${quote.id}?step=${closeStep}`
                  : `/quotes/${quote.id}?step=documents${
                      currentNonPanelStep ? `&from=${currentNonPanelStep}` : ""
                    }`
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
