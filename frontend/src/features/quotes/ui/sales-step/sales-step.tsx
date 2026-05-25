"use client";

import { useEffect, useState } from "react";
import { AppToaster } from "@/shared/ui/app-toaster";
import type { QuoteDetailRow, QuoteItemRow } from "@/entities/quote/queries";
import { createClient } from "@/shared/lib/supabase/client";
import { canEditQuoteCustomerFields } from "@/shared/lib/roles";
import { SalesActionBar } from "./sales-action-bar";
import type { ClientResponseModal } from "./sales-action-bar";
import { SalesItemsTable, type SalesItemRow } from "./sales-items-table";
import { SalesItemsEditor } from "./sales-items-editor";
import { ClientResponseModals } from "./client-response-modals";
import { DistributionCommentInline } from "./distribution-comment-inline";

interface SalesStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  userRoles: string[];
}

/**
 * Shape of the JSONB `kvota.quotes.sales_checklist` payload. Re-declared here
 * (narrowed to only the field we read) instead of importing from
 * `context-panel/sales-checklist-block` to keep the sales-step bundle from
 * pulling the context-panel chunk.
 */
interface SalesChecklistJsonb {
  distribution_comment?: string | null;
}

export function SalesStep({ quote, items, userRoles }: SalesStepProps) {
  const [activeModal, setActiveModal] = useState<ClientResponseModal>(null);
  const isDraft = (quote.workflow_status ?? "draft") === "draft";
  // Mirror the customer-field edit gate (admin / sales / head_of_sales) for
  // the inline editor. Testing 2 row 61: МОП / РОП need to amend the field
  // both pre- and post-transfer; other roles see it read-only.
  const canEditDistributionComment = canEditQuoteCustomerFields(userRoles);
  const distributionComment =
    (
      (quote.sales_checklist as SalesChecklistJsonb | null) ?? null
    )?.distribution_comment ?? null;

  // Phase 5d: base_price_vat moved from quote_items to invoice_items.
  // For read-only views (non-draft), project the composed price per
  // quote_item from invoice_item_coverage -> invoice_items filtered to
  // composition_selected_invoice_id.
  const salesRows = useSalesItemRows(items);

  return (
    <div className="flex-1 min-w-0">
      <SalesActionBar quote={quote} items={items} onOpenModal={setActiveModal} />
      <div className="p-6 space-y-6">
        {/* Testing 2 row 61 (МОП / РОП «Нет поля 21.05.2026»): surface the
            distribution comment above the positions grid so it's actually
            discoverable + editable post-transfer. Modal in transfer-dialog
            remains as fallback path. For sales-tier the editor is always
            visible (even when empty) so the affordance is impossible to miss;
            for read-only roles we render the comment only when it carries
            content — empty block on every quote would just be noise. */}
        {(canEditDistributionComment || (distributionComment ?? "").trim().length > 0) && (
          <DistributionCommentInline
            quoteId={quote.id}
            initialValue={distributionComment}
            canEdit={canEditDistributionComment}
          />
        )}
        {isDraft ? (
          <SalesItemsEditor
            quoteId={quote.id}
            items={items}
            currency={quote.currency ?? "USD"}
          />
        ) : (
          <SalesItemsTable
            items={salesRows}
            currency={quote.currency ?? "USD"}
            quoteId={quote.id}
          />
        )}
      </div>
      <ClientResponseModals
        quoteId={quote.id}
        idnQuote={quote.idn_quote}
        activeModal={activeModal}
        onClose={() => setActiveModal(null)}
      />
      <AppToaster />
    </div>
  );
}

function useSalesItemRows(items: QuoteItemRow[]): SalesItemRow[] {
  const [rows, setRows] = useState<SalesItemRow[]>(() =>
    items.map(toPlaceholderSalesRow)
  );

  useEffect(() => {
    if (items.length === 0) {
      setRows([]);
      return;
    }
    const supabase = createClient();
    let cancelled = false;

    async function load() {
      const qiIds = items.map((it) => it.id);
      const { data, error } = await supabase
        .from("invoice_item_coverage")
        .select(
          "quote_item_id, invoice_items!inner(invoice_id, base_price_vat)"
        )
        .in("quote_item_id", qiIds);

      if (cancelled) return;

      if (error) {
        console.error("Failed to load invoice_items coverage for sales:", error);
        setRows(items.map(toPlaceholderSalesRow));
        return;
      }

      const priceByQi = new Map<string, number | null>();
      for (const row of (data ?? []) as unknown as Array<{
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

      setRows(
        items.map((it) => ({
          id: it.id,
          brand: it.brand,
          product_code: it.product_code,
          product_name: it.product_name,
          quantity: it.quantity,
          unit: it.unit,
          base_price_vat: priceByQi.get(it.id) ?? null,
        }))
      );
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [items]);

  return rows;
}

function toPlaceholderSalesRow(item: QuoteItemRow): SalesItemRow {
  return {
    id: item.id,
    brand: item.brand,
    product_code: item.product_code,
    product_name: item.product_name,
    quantity: item.quantity,
    unit: item.unit,
    base_price_vat: null,
  };
}
