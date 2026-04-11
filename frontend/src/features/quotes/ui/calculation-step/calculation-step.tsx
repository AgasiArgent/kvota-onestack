"use client";

import { useState, useCallback } from "react";
import { Toaster } from "sonner";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";
import { CalculationForm } from "./calculation-form";
import { CalculationResults } from "./calculation-results";
import { CalculationActionBar } from "./calculation-action-bar";
import { CompositionPicker } from "./composition-picker";

interface CalculationStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  userRoles: string[];
  savedVariables: Record<string, unknown> | null;
}

export function CalculationStep({
  quote,
  items,
  savedVariables,
}: CalculationStepProps) {
  const [formValues, setFormValues] = useState<Record<string, string>>(() =>
    buildInitialValues(quote, savedVariables)
  );

  const handleFieldChange = useCallback(
    (key: string, value: string) => {
      setFormValues((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  const hasCalculation =
    (quote as Record<string, unknown>).total_quote_currency != null;

  return (
    <div className="flex-1 min-w-0">
      <CalculationActionBar
        quoteId={quote.id}
        formValues={formValues}
        hasCalculation={hasCalculation}
        workflowStatus={quote.workflow_status ?? "draft"}
        isApproved={["approved", "sent_to_client", "accepted"].includes(quote.workflow_status ?? "")}
      />
      <div className="p-6 space-y-6">
        <CalculationForm
          quote={quote}
          savedVariables={savedVariables}
          formValues={formValues}
          onFieldChange={handleFieldChange}
        />
        {/* Phase 5b — Multi-supplier composition picker (renders nothing
            when there is no multi-supplier choice to make). */}
        <CompositionPicker quoteId={quote.id} />
        <CalculationResults quote={quote} items={items} />
      </div>
      <Toaster position="top-right" richColors />
    </div>
  );
}

function buildInitialValues(
  quote: QuoteDetailRow,
  saved: Record<string, unknown> | null
): Record<string, string> {
  function sv(key: string, fallback: string | number): string {
    if (saved && saved[key] != null) return String(saved[key]);
    return String(fallback);
  }

  const quoteCurrency = quote.currency ?? "USD";

  return {
    // Company & terms
    offer_sale_type: sv("offer_sale_type", "поставка"),
    offer_incoterms: sv("offer_incoterms", "DDP"),
    currency: sv("currency_of_quote", quoteCurrency),
    // Markup
    markup: sv("markup", "15"),
    // Hidden fields (carried through from saved variables)
    supplier_discount: sv("supplier_discount", "0"),
    exchange_rate: sv("exchange_rate", "1.0"),
    delivery_time: sv("delivery_time", "30"),
    seller_company: sv("seller_company", ""),
    // Logistics (hidden, aggregated from invoices by Python)
    logistics_supplier_hub: sv("logistics_supplier_hub", "0"),
    logistics_hub_customs: sv("logistics_hub_customs", "0"),
    logistics_customs_client: sv("logistics_customs_client", "0"),
    // Brokerage (hidden, set in customs step)
    brokerage_hub: sv("brokerage_hub", "0"),
    brokerage_hub_currency: sv("brokerage_hub_currency", "RUB"),
    brokerage_customs: sv("brokerage_customs", "0"),
    brokerage_customs_currency: sv("brokerage_customs_currency", "RUB"),
    warehousing_at_customs: sv("warehousing_at_customs", "0"),
    warehousing_at_customs_currency: sv(
      "warehousing_at_customs_currency",
      "RUB"
    ),
    customs_documentation: sv("customs_documentation", "0"),
    customs_documentation_currency: sv(
      "customs_documentation_currency",
      "RUB"
    ),
    brokerage_extra: sv("brokerage_extra", "0"),
    brokerage_extra_currency: sv("brokerage_extra_currency", "RUB"),
    advance_to_supplier: sv("advance_to_supplier", "100"),
    // Payment terms
    advance_from_client: sv("advance_from_client", "100"),
    time_to_advance: sv("time_to_advance", "0"),
    time_to_advance_on_receiving: sv("time_to_advance_on_receiving", "0"),
    // DM fee
    dm_fee_type: sv("dm_fee_type", "fixed"),
    dm_fee_value: sv("dm_fee_value", "0"),
    dm_fee_currency: sv("dm_fee_currency", "RUB"),
  };
}
