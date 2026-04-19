"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { completeLogistics } from "@/entities/quote/mutations";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { createClient } from "@/shared/lib/supabase/client";
import { LogisticsActionBar } from "./logistics-action-bar";
import { LogisticsInvoiceRow } from "./logistics-invoice-row";
import type { LogisticsProductRow } from "./products-subtable";

interface LogisticsStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  userRoles: string[];
}

export function LogisticsStep({
  quote,
  invoices,
}: LogisticsStepProps) {
  const router = useRouter();
  const [completing, setCompleting] = useState(false);

  // Phase 5d: per-invoice logistics rows read from invoice_items
  // (supplier-side weight + dimensions). quote_items.invoice_id/weight_in_kg
  // are dropped in migration 284, so the mapping must come through the
  // supplier-side table.
  const invoiceItemsMap = useInvoiceItemsByInvoiceId(invoices);

  const deliveryCity = quote.delivery_city ?? null;

  async function handleCompleteLogistics() {
    setCompleting(true);
    try {
      await completeLogistics(quote.id);
      toast.success("Логистика завершена");
      router.refresh();
    } catch {
      toast.error("Не удалось завершить логистику");
    } finally {
      setCompleting(false);
    }
  }

  return (
    <div className="flex-1 min-w-0">
      <LogisticsActionBar
        invoices={invoices}
        onCompleteLogistics={handleCompleteLogistics}
        completing={completing}
      />

      <div className="p-6 space-y-4">
        {invoices.map((invoice, idx) => (
          <LogisticsInvoiceRow
            key={invoice.id}
            invoice={invoice}
            items={invoiceItemsMap.get(invoice.id) ?? []}
            deliveryCity={deliveryCity}
            defaultExpanded={invoices.length === 1 && idx === 0}
          />
        ))}

        {invoices.length === 0 && (
          <div className="text-center py-12 text-muted-foreground">
            Нет инвойсов для логистики. Сначала завершите закупку.
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Phase 5d — per-invoice product rows sourced from invoice_items (the
 * supplier-side table). Provides the narrow shape the ProductsSubtable
 * needs (product_name, product_code, quantity, weight + dimensions).
 */
function useInvoiceItemsByInvoiceId(
  invoices: QuoteInvoiceRow[]
): Map<string, LogisticsProductRow[]> {
  const [map, setMap] = useState<Map<string, LogisticsProductRow[]>>(
    new Map()
  );

  useEffect(() => {
    if (invoices.length === 0) {
      setMap(new Map());
      return;
    }
    // database.types.ts does not yet include invoice_items (added by
    // migration 281). Cast through `from` until the next type regen.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const untyped = createClient() as unknown as { from: (t: string) => any };
    let cancelled = false;

    async function load() {
      const invoiceIds = invoices.map((inv) => inv.id);
      const { data, error } = await untyped
        .from("invoice_items")
        .select(
          "id, invoice_id, product_name, supplier_sku, quantity, weight_in_kg, dimension_height_mm, dimension_width_mm, dimension_length_mm"
        )
        .in("invoice_id", invoiceIds);

      if (cancelled) return;

      if (error) {
        console.error("Failed to load invoice_items for logistics:", error);
        setMap(new Map());
        return;
      }

      const byInvoice = new Map<string, LogisticsProductRow[]>();
      for (const row of (data ?? []) as Array<{
        id: string;
        invoice_id: string;
        product_name: string;
        supplier_sku: string | null;
        quantity: number;
        weight_in_kg: number | null;
        dimension_height_mm: number | null;
        dimension_width_mm: number | null;
        dimension_length_mm: number | null;
      }>) {
        const list = byInvoice.get(row.invoice_id) ?? [];
        list.push({
          id: row.id,
          product_name: row.product_name,
          product_code: row.supplier_sku,
          quantity: row.quantity,
          weight_in_kg: row.weight_in_kg,
          dimension_height_mm: row.dimension_height_mm,
          dimension_width_mm: row.dimension_width_mm,
          dimension_length_mm: row.dimension_length_mm,
        });
        byInvoice.set(row.invoice_id, list);
      }
      setMap(byInvoice);
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [invoices]);

  return map;
}
