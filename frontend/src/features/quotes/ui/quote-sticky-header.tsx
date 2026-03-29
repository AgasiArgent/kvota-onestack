"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { QuoteDetailRow } from "@/entities/quote/queries";

const STATUS_BADGE_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700",
  pending_procurement: "bg-amber-100 text-amber-700",
  procurement_complete: "bg-amber-100 text-amber-700",
  calculated: "bg-blue-100 text-blue-700",
  pending_approval: "bg-blue-100 text-blue-700",
  pending_quote_control: "bg-blue-100 text-blue-700",
  pending_spec_control: "bg-blue-100 text-blue-700",
  pending_sales_review: "bg-blue-100 text-blue-700",
  approved: "bg-green-100 text-green-700",
  sent_to_client: "bg-green-100 text-green-700",
  accepted: "bg-green-200 text-green-800 font-semibold",
  spec_signed: "bg-green-200 text-green-800 font-semibold",
  rejected: "bg-red-100 text-red-700",
  cancelled: "bg-red-100 text-red-700",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  pending_procurement: "На закупке",
  procurement_complete: "Закупка завершена",
  calculated: "Рассчитано",
  pending_approval: "На согласовании",
  pending_quote_control: "Контроль КП",
  pending_spec_control: "Контроль спецификации",
  pending_sales_review: "Ревью продаж",
  approved: "Одобрено",
  sent_to_client: "Отправлено клиенту",
  accepted: "Принято",
  spec_signed: "Сделка",
  rejected: "Отклонено",
  cancelled: "Отменено",
};

interface QuoteStickyHeaderProps {
  quote: QuoteDetailRow;
  isAdmin: boolean;
}

export function QuoteStickyHeader({ quote }: QuoteStickyHeaderProps) {
  const workflowStatus = quote.workflow_status ?? "draft";
  const statusStyle =
    STATUS_BADGE_STYLES[workflowStatus] ?? "bg-slate-100 text-slate-700";
  const statusLabel = STATUS_LABELS[workflowStatus] ?? workflowStatus;

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

          {quote.customer && (
            <Link
              href={`/customers/${quote.customer.id}`}
              className="text-sm text-muted-foreground hover:text-accent truncate"
            >
              {quote.customer.name}
            </Link>
          )}
        </div>

        {/* Right: amount + margin (info only, no action buttons) */}
        <div className="flex items-center gap-4 shrink-0">
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
        </div>
      </div>
    </div>
  );
}
