"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { completeCustoms, skipCustoms } from "@/entities/quote/mutations";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { createClient } from "@/shared/lib/supabase/client";
import { CustomsActionBar } from "./customs-action-bar";
import { CustomsItemsEditor } from "./customs-items-editor";
import { CustomsExpenses } from "./customs-expenses";
import { CustomsNotes } from "./customs-notes";
import { CustomsInfoBlock } from "./customs-info-block";

function ext<T>(row: unknown): T {
  return row as T;
}

function useSupplierByQuoteItemId(
  items: QuoteItemRow[]
): Map<
  string,
  { supplier_country: string | null; invoice_id: string | null }
> {
  const [map, setMap] = useState<
    Map<
      string,
      { supplier_country: string | null; invoice_id: string | null }
    >
  >(new Map());

  useEffect(() => {
    if (items.length === 0) {
      setMap(new Map());
      return;
    }
    const supabase = createClient();
    let cancelled = false;

    async function load() {
      const qiIds = items.map((it) => it.id);
      const { data, error } = await supabase
        .from("invoice_item_coverage")
        .select(
          "quote_item_id, invoice_items!inner(invoice_id, supplier_country)"
        )
        .in("quote_item_id", qiIds);

      if (cancelled) return;

      if (error) {
        console.error(
          "Failed to load invoice_items coverage for customs:",
          error
        );
        setMap(new Map());
        return;
      }

      const rowsByQi = new Map<
        string,
        Array<{ invoice_id: string; supplier_country: string | null }>
      >();
      for (const row of (data ?? []) as unknown as Array<{
        quote_item_id: string;
        invoice_items: {
          invoice_id: string;
          supplier_country: string | null;
        };
      }>) {
        const list = rowsByQi.get(row.quote_item_id) ?? [];
        list.push(row.invoice_items);
        rowsByQi.set(row.quote_item_id, list);
      }

      const result = new Map<
        string,
        { supplier_country: string | null; invoice_id: string | null }
      >();
      for (const qi of items) {
        const selected = qi.composition_selected_invoice_id ?? null;
        const candidates = rowsByQi.get(qi.id) ?? [];
        const match =
          candidates.find((c) =>
            selected == null ? true : c.invoice_id === selected
          ) ?? null;
        result.set(qi.id, {
          supplier_country: match?.supplier_country ?? null,
          invoice_id: match?.invoice_id ?? null,
        });
      }
      setMap(result);
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [items]);

  return map;
}

interface CustomsStepProps {
  quote: QuoteDetailRow;
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  userRoles: string[];
}

export function CustomsStep({
  quote,
  items,
  invoices,
  userRoles,
}: CustomsStepProps) {
  const router = useRouter();
  const [completing, setCompleting] = useState(false);
  const [skipping, setSkipping] = useState(false);

  const isPendingCustoms = quote.workflow_status === "pending_customs";
  const canSkipCustoms =
    isPendingCustoms &&
    userRoles.some((r) => r === "customs" || r === "admin");

  const invoiceCountryMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const inv of invoices) {
      if (inv.pickup_country) {
        map.set(inv.id, inv.pickup_country);
      }
    }
    return map;
  }, [invoices]);

  // Phase 5d: supplier_country + invoice_id now live on invoice_items.
  // Project them per quote_item via invoice_item_coverage, filtered by
  // composition_selected_invoice_id (or first covering invoice if no
  // explicit selection has been made).
  const supplierByQuoteItemId = useSupplierByQuoteItemId(items);

  const customsNotes = ext<{ customs_notes?: string | null }>(quote).customs_notes ?? "";

  async function handleCompleteCustoms() {
    setCompleting(true);
    try {
      await completeCustoms(quote.id);
      toast.success("Таможня завершена");
      router.refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось завершить таможню"
      );
    } finally {
      setCompleting(false);
    }
  }

  async function handleSkipCustoms() {
    setSkipping(true);
    try {
      await skipCustoms(quote.id);
      toast.success("Таможня пропущена");
      router.refresh();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Не удалось пропустить таможню"
      );
    } finally {
      setSkipping(false);
    }
  }

  return (
    <div className="flex-1 min-w-0">
      <CustomsActionBar
        items={items}
        onCompleteCustoms={handleCompleteCustoms}
        onSkipCustoms={handleSkipCustoms}
        completing={completing}
        skipping={skipping}
        canSkipCustoms={canSkipCustoms}
      />

      <div className="p-6 space-y-4">
        <CustomsItemsEditor
          items={items}
          invoiceCountryMap={invoiceCountryMap}
          supplierByQuoteItemId={supplierByQuoteItemId}
          userRoles={userRoles}
        />

        <CustomsExpenses quoteId={quote.id} />

        <CustomsNotes quoteId={quote.id} initialNotes={customsNotes} />

        <CustomsInfoBlock quoteId={quote.id} orgId={quote.organization_id} />
      </div>
    </div>
  );
}
