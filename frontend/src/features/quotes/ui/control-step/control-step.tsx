"use client";

import { useMemo, useEffect, useState } from "react";
import { Toaster } from "sonner";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { createClient } from "@/shared/lib/supabase/client";
import { useControlData } from "./use-control-data";
import { useControlChecks } from "./use-control-checks";
import { WorkflowStatusBanner } from "./workflow-status-banner";
import { DealSummaryPanel } from "./deal-summary-panel";
import { VerificationStrip } from "./verification-strip";
import { CalcSummaryRow } from "./calc-summary-row";
import { InvoiceComparisonPanel } from "./invoice-comparison-panel";
import { ControlActionBar } from "./control-action-bar";

const ALLOWED_ROLES = [
  "quote_controller",
  "spec_controller",
  "admin",
  "top_manager",
];

interface ControlStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  userRoles: string[];
  calcVariables: Record<string, unknown> | null;
}

function getVar(
  vars: Record<string, unknown> | null,
  key: string,
): unknown {
  return vars?.[key] ?? null;
}

function toNumber(value: unknown, fallback: number = 0): number {
  if (value == null) return fallback;
  const n = Number(value);
  return isNaN(n) ? fallback : n;
}

export function ControlStep({
  quote,
  items,
  invoices,
  userRoles,
  calcVariables,
}: ControlStepProps) {
  // Access control
  const hasAccess = userRoles.some((r) => ALLOWED_ROLES.includes(r));

  // Get current user ID from Supabase auth (avoids prop-drilling through QuoteStepContent)
  const [userId, setUserId] = useState<string>("");
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      if (data.user) setUserId(data.user.id);
    });
  }, []);

  // Invoice IDs for data fetching
  const invoiceIds = useMemo(
    () => invoices.map((inv) => inv.id),
    [invoices],
  );

  // Fetch additional data (calc summaries, documents)
  const { calcSummary, invoiceDocuments, isLoading } = useControlData(
    quote.id,
    invoiceIds,
  );

  // Compute 7 verification checks
  const checks = useControlChecks(
    quote,
    items,
    calcVariables,
    calcSummary,
    invoiceDocuments,
  );

  // Extract values for panels
  const workflowStatus = quote.workflow_status ?? "draft";
  const currency = quote.currency ?? "USD";
  const markup = toNumber(getVar(calcVariables, "markup"));
  const dealType = (getVar(calcVariables, "offer_sale_type") as string) ?? quote.deal_type ?? null;
  const incoterms = (getVar(calcVariables, "offer_incoterms") as string) ?? null;
  const clientPrepayment = toNumber(getVar(calcVariables, "advance_from_client"), 100);
  const supplierAdvance = toNumber(getVar(calcVariables, "supplier_advance"));
  const lprReward = toNumber(getVar(calcVariables, "lpr_reward")) + toNumber(getVar(calcVariables, "decision_maker_reward"));
  const totalAmount = quote.total_amount_quote ?? null;

  // Financing amount & import VAT from calc summary
  const financingAmount = calcSummary
    ? toNumber(calcSummary.calc_ae16_sale_price_total) - toNumber(calcSummary.calc_s16_total_purchase_price)
    : null;
  const importVat = calcSummary
    ? toNumber((calcSummary as unknown as Record<string, unknown>)["calc_z16_total_import_vat"])
    : null;

  // Calc summary values
  const totalPurchase = calcSummary?.calc_s16_total_purchase_price ?? null;
  const totalCogs = calcSummary?.calc_ab16_cogs_total ?? null;
  const totalLogistics = calcSummary?.calc_v16_total_logistics ?? null;
  const totalSaleWithVat = calcSummary?.calc_al16_total_with_vat ?? null;
  const marginPercent = calcSummary?.calc_af16_profit_margin ?? null;

  // Approval triggers
  const approvalTriggers = useMemo(() => {
    const triggers: string[] = [];
    if (currency === "RUB") triggers.push("Валюта КП = рубли");
    if (clientPrepayment < 100) triggers.push(`Не 100% предоплата (${clientPrepayment}%)`);

    const minMarkup = dealType === "transit" ? 8 : 12;
    if (markup < minMarkup) {
      const typeLabel = dealType === "transit" ? "транзита" : "поставки";
      triggers.push(`Наценка (${markup}%) ниже минимума для ${typeLabel} (${minMarkup}%)`);
    }

    if (lprReward > 0) triggers.push(`Есть вознаграждение ЛПРа (${lprReward})`);
    return triggers;
  }, [currency, clientPrepayment, markup, dealType, lprReward]);

  if (!hasAccess) {
    return (
      <div className="flex-1 p-6">
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          Нет доступа к контролю КП. Требуется роль контролёра или администратора.
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex-1 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-16 rounded-lg bg-muted" />
          <div className="h-24 rounded-lg bg-muted" />
          <div className="h-12 rounded-lg bg-muted" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 min-w-0 pb-20">
      <div className="p-6 space-y-4">
        <WorkflowStatusBanner
          workflowStatus={workflowStatus}
          approvalTriggers={approvalTriggers}
        />

        <DealSummaryPanel
          dealType={dealType}
          incoterms={incoterms}
          currency={currency}
          markup={markup}
          itemCount={items.length}
          clientPrepayment={clientPrepayment}
          supplierAdvance={supplierAdvance}
          totalAmount={totalAmount}
          financingAmount={financingAmount}
          importVat={importVat}
        />

        <VerificationStrip checks={checks} />

        <CalcSummaryRow
          totalPurchase={totalPurchase}
          totalCogs={totalCogs}
          totalLogistics={totalLogistics}
          totalSaleWithVat={totalSaleWithVat}
          marginPercent={marginPercent}
          currency={currency}
          quoteId={quote.id}
        />

        <InvoiceComparisonPanel
          quoteId={quote.id}
          invoices={invoices}
          items={items}
          invoiceDocuments={invoiceDocuments}
        />
      </div>

      <ControlActionBar
        quoteId={quote.id}
        userId={userId}
        workflowStatus={workflowStatus}
        needsApproval={approvalTriggers.length > 0}
      />

      <Toaster position="top-right" richColors />
    </div>
  );
}
