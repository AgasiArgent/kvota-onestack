"use client";

import { useState, useCallback, useEffect } from "react";
import { Toaster } from "sonner";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";
import { CalculationForm } from "./calculation-form";
import {
  CalculationResults,
  type CalculationResultsItem,
} from "./calculation-results";
import { CalculationActionBar } from "./calculation-action-bar";
import { CompositionPicker } from "./composition-picker";
import { createClient } from "@/shared/lib/supabase/client";

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
  // Phase 5d: base_price_vat lives on invoice_items, not quote_items. Load
  // it from the per-quote-item selected invoice and project onto the narrow
  // CalculationResultsItem shape for the results table.
  const [resultsItems, setResultsItems] = useState<CalculationResultsItem[]>(
    () => items.map(toPlaceholderResultItem)
  );

  useEffect(() => {
    // database.types.ts does not yet include invoice_items / coverage
    // (added by migrations 281-282). Cast through `from` to bypass the
    // missing types until the next regeneration.
    const supabase = createClient();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const untyped = supabase as unknown as { from: (t: string) => any };

    let cancelled = false;

    async function load() {
      const qiIds = items.map((it) => it.id);
      if (qiIds.length === 0) {
        if (!cancelled) setResultsItems([]);
        return;
      }

      const { data: cov, error } = await untyped
        .from("invoice_item_coverage")
        .select(
          "quote_item_id, invoice_items!inner(invoice_id, base_price_vat)"
        )
        .in("quote_item_id", qiIds);

      if (cancelled) return;

      if (error) {
        console.error("Failed to load invoice_items coverage:", error);
        setResultsItems(items.map(toPlaceholderResultItem));
        return;
      }

      // For each quote_item, find the row whose invoice matches
      // composition_selected_invoice_id (null-case: first coverage row wins,
      // so the renderer still shows a value even when selection is implicit).
      const priceByQi = new Map<string, number | null>();
      for (const row of (cov ?? []) as Array<{
        quote_item_id: string;
        invoice_items: { invoice_id: string; base_price_vat: number | null };
      }>) {
        const qi = items.find((it) => it.id === row.quote_item_id);
        if (!qi) continue;
        const selected = qi.composition_selected_invoice_id ?? null;
        if (selected != null && row.invoice_items.invoice_id !== selected)
          continue;
        if (!priceByQi.has(row.quote_item_id)) {
          priceByQi.set(
            row.quote_item_id,
            row.invoice_items.base_price_vat ?? null
          );
        }
      }

      setResultsItems(
        items.map((it) => ({
          id: it.id,
          product_name: it.product_name,
          brand: it.brand,
          quantity: it.quantity ?? null,
          base_price_vat: priceByQi.get(it.id) ?? null,
        }))
      );
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [items]);

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
        <CalculationResults quote={quote} items={resultsItems} />
      </div>
      <Toaster position="top-right" richColors />
    </div>
  );
}

function toPlaceholderResultItem(item: QuoteItemRow): CalculationResultsItem {
  // Initial render before invoice_items coverage is loaded. base_price_vat is
  // null until the async fetch completes; the renderer already handles null.
  return {
    id: item.id,
    product_name: item.product_name,
    brand: item.brand,
    quantity: item.quantity ?? null,
    base_price_vat: null,
  };
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
