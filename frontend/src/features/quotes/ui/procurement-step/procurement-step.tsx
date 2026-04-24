"use client";

import { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { createClient } from "@/shared/lib/supabase/client";
import { extractErrorMessage } from "@/shared/lib/errors";
import { completeProcurement } from "@/entities/quote/mutations";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { ProcurementActionBar } from "./procurement-action-bar";
import { QuotePositionsList } from "./quote-positions-list";
import { InvoiceCard } from "./invoice-card";
import { InvoiceCreateModal } from "./invoice-create-modal";

/**
 * Phase 5d Task 14 — "can complete procurement" guard.
 *
 * Legacy check read `items.purchase_price_original` off quote_items (dropped
 * in migration 284). The new guard delegates to a caller-supplied map of
 * coverage readiness: `priceReadyByQuoteItemId[qi.id] === true` iff at
 * least one covering invoice_item in the selected invoice has a non-null
 * `purchase_price_original`. Items marked `is_unavailable` are exempt.
 */
export type PriceReadyMap = Record<string, boolean>;

export interface CompleteGuardItem {
  id: string;
  invoice_id: string | null;
  is_unavailable: boolean;
}

export type CompleteGuardResult =
  | { ok: true }
  | { ok: false; reason: "no-price" | "unassigned"; count: number };

export function validateCompleteProcurementGuard(
  items: CompleteGuardItem[],
  priceReadyByQuoteItemId: PriceReadyMap
): CompleteGuardResult {
  const noPriceCount = items.filter(
    (i) =>
      i.is_unavailable !== true &&
      priceReadyByQuoteItemId[i.id] !== true
  ).length;
  if (noPriceCount > 0) {
    return { ok: false, reason: "no-price", count: noPriceCount };
  }

  const unassignedCount = items.filter(
    (i) => !i.invoice_id && i.is_unavailable !== true
  ).length;
  if (unassignedCount > 0) {
    return { ok: false, reason: "unassigned", count: unassignedCount };
  }

  return { ok: true };
}

interface Supplier {
  id: string;
  name: string;
  country: string | null;
}

interface BuyerCompany {
  id: string;
  name: string;
  company_code: string;
}

interface ProcurementStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  userRoles?: string[];
}

export function ProcurementStep({
  quote,
  items,
  invoices,
  userRoles = [],
}: ProcurementStepProps) {
  const router = useRouter();
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [preselectedItemIds, setPreselectedItemIds] = useState<string[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [buyerCompanies, setBuyerCompanies] = useState<BuyerCompany[]>([]);
  const [completing, setCompleting] = useState(false);
  // Phase 5d: coverage-derived readiness. Map: quote_item_id → has at least
  // one covering invoice_item in its selected invoice with non-null
  // purchase_price_original. Post-migration 284 this replaces reading the
  // dropped `quote_items.purchase_price_original` column.
  const [priceReadyByQuoteItemId, setPriceReadyByQuoteItemId] =
    useState<PriceReadyMap>({});
  // Phase 5d: quote_items.invoice_id was dropped in migration 284. Map
  // quote_item → invoice_id via invoice_item_coverage, selecting the row
  // in each quote_item's composition_selected_invoice_id (or the first
  // covering invoice when no selection has been made).
  const [invoiceIdByQuoteItemId, setInvoiceIdByQuoteItemId] = useState<
    Record<string, string | null>
  >({});
  // Phase 5d: quote_items.min_order_quantity was dropped in migration 284.
  // Project the MOQ from the covering invoice_item (selected invoice wins).
  const [minOrderQuantityByQuoteItemId, setMinOrderQuantityByQuoteItemId] =
    useState<Record<string, number | null>>({});

  // Load suppliers and buyer companies for the invoice creation modal
  useEffect(() => {
    const supabase = createClient();

    supabase
      .from("suppliers")
      .select("id, name, country")
      .eq("organization_id", quote.organization_id)
      .order("name")
      .then(({ data }) => setSuppliers(data ?? []));

    supabase
      .from("buyer_companies")
      .select("id, name, company_code")
      .eq("organization_id", quote.organization_id)
      .order("name")
      .then(({ data }) => setBuyerCompanies(data ?? []));
  }, [quote.organization_id]);

  // Phase 5d: derive priceReady from invoice_item_coverage → invoice_items.
  useEffect(() => {
    if (items.length === 0) {
      setPriceReadyByQuoteItemId({});
      return;
    }
    const supabase = createClient();

    let cancelled = false;
    void (async () => {
      const qiIds = items.map((i) => i.id);
      const { data } = await supabase
        .from("invoice_item_coverage")
        .select(
          "quote_item_id, invoice_items!inner(invoice_id, purchase_price_original, minimum_order_quantity)"
        )
        .in("quote_item_id", qiIds);
      if (cancelled) return;
      const selectedByQi = new Map<string, string | null>();
      for (const qi of items) {
        selectedByQi.set(
          qi.id,
          (qi as unknown as { composition_selected_invoice_id: string | null })
            .composition_selected_invoice_id ?? null
        );
      }
      const ready: PriceReadyMap = {};
      const invoiceIdMap: Record<string, string | null> = {};
      const moqMap: Record<string, number | null> = {};
      for (const row of (data ?? []) as unknown as Array<{
        quote_item_id: string;
        invoice_items: {
          invoice_id: string;
          purchase_price_original: number | null;
          minimum_order_quantity: number | null;
        };
      }>) {
        const selected = selectedByQi.get(row.quote_item_id);
        const isSelectedRow =
          !!selected && row.invoice_items?.invoice_id === selected;
        if (isSelectedRow && row.invoice_items?.purchase_price_original != null) {
          ready[row.quote_item_id] = true;
        }
        // Pin invoice_id + MOQ from the selected row when it exists, else
        // take the first covering row.
        const take = isSelectedRow || !selected;
        if (take && invoiceIdMap[row.quote_item_id] === undefined) {
          invoiceIdMap[row.quote_item_id] =
            row.invoice_items?.invoice_id ?? null;
          moqMap[row.quote_item_id] =
            row.invoice_items?.minimum_order_quantity ?? null;
        }
      }
      setPriceReadyByQuoteItemId(ready);
      setInvoiceIdByQuoteItemId(invoiceIdMap);
      setMinOrderQuantityByQuoteItemId(moqMap);
    })();
    return () => {
      cancelled = true;
    };
  }, [items]);

  const invoiceItemsMap = useMemo(() => {
    const map = new Map<string, QuoteItemRow[]>();
    for (const item of items) {
      const invId = invoiceIdByQuoteItemId[item.id] ?? null;
      if (invId != null) {
        const existing = map.get(invId) ?? [];
        existing.push(item);
        map.set(invId, existing);
      }
    }
    return map;
  }, [items, invoiceIdByQuoteItemId]);

  function handleCreateInvoice() {
    setPreselectedItemIds([]);
    setCreateModalOpen(true);
  }

  function handleCreateInvoiceWithItems(itemIds: string[]) {
    setPreselectedItemIds(itemIds);
    setCreateModalOpen(true);
  }

  async function handleCompleteProcurement() {
    const guard = validateCompleteProcurementGuard(
      items.map((i) => ({
        id: i.id,
        invoice_id: invoiceIdByQuoteItemId[i.id] ?? null,
        is_unavailable: i.is_unavailable === true,
      })),
      priceReadyByQuoteItemId
    );
    if (!guard.ok) {
      if (guard.reason === "no-price") {
        toast.error(
          `Нельзя завершить: ${guard.count} поз. без цены. Заполните цену или отметьте Н/Д.`
        );
      } else {
        toast.error(
          `Нельзя завершить: ${guard.count} поз. не распределены по КП поставщиков.`
        );
      }
      return;
    }

    setCompleting(true);
    try {
      await completeProcurement(quote.id);
      toast.success("Закупка завершена");
      router.refresh();
    } catch (err) {
      console.error("[procurement-step] complete procurement failed:", err);
      toast.error(extractErrorMessage(err) ?? "Не удалось завершить закупку");
    } finally {
      setCompleting(false);
    }
  }

  const preselectedItems = items.filter((i) =>
    preselectedItemIds.includes(i.id)
  );

  return (
    <div className="flex-1 min-w-0">
      <ProcurementActionBar
        items={items}
        priceReadyByQuoteItemId={priceReadyByQuoteItemId}
        invoiceIdByQuoteItemId={invoiceIdByQuoteItemId}
        minOrderQuantityByQuoteItemId={minOrderQuantityByQuoteItemId}
        onCreateInvoice={handleCreateInvoice}
        onCompleteProcurement={handleCompleteProcurement}
        completing={completing}
        procurementCompleted={quote.procurement_completed_at != null}
      />

      <div className="p-6 space-y-4">
        <QuotePositionsList
          key={invoices.length}
          items={items}
          invoices={invoices}
          onCreateInvoiceWithItems={handleCreateInvoiceWithItems}
        />

        {invoices.map((invoice) => (
          <InvoiceCard
            key={invoice.id}
            invoice={invoice}
            items={invoiceItemsMap.get(invoice.id) ?? []}
            quote={quote}
            defaultExpanded={invoices.length === 1}
            userRoles={userRoles}
          />
        ))}

        {invoices.length === 0 && items.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            Нет КП поставщиков
          </div>
        )}
      </div>

      <InvoiceCreateModal
        open={createModalOpen}
        onClose={() => { setCreateModalOpen(false); setPreselectedItemIds([]); }}
        quoteId={quote.id}
        idnQuote={quote.idn_quote}
        selectedItems={preselectedItems}
        suppliers={suppliers}
        buyerCompanies={buyerCompanies}
      />
    </div>
  );
}
