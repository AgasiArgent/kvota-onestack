"use client";

import { useCallback, useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { completeCustoms, skipCustoms } from "@/entities/quote/mutations";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { createClient } from "@/shared/lib/supabase/client";
import {
  AutofillBanner,
  type CustomsAutofillSuggestion,
} from "@/features/customs-autofill";
import { CustomsActionBar } from "./customs-action-bar";
import { CustomsItemsEditor } from "./customs-items-editor";
import { CustomsExpenses } from "./customs-expenses";
import { CustomsNotes } from "./customs-notes";
import { EntityNotesPanel } from "@/entities/entity-note";
import type { EntityNoteCardData } from "@/entities/entity-note/ui/entity-note-card";
import { CustomsInfoBlock } from "./customs-info-block";
import { QuoteCustomsExpenses } from "./quote-customs-expenses";
import { ItemCustomsExpenses } from "./item-customs-expenses";
import { CustomsItemDialog } from "./customs-item-dialog";

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
  userId?: string;
  quoteNotes?: EntityNoteCardData[];
}

export function CustomsStep({
  quote,
  items,
  invoices,
  userRoles,
  userId,
  quoteNotes = [],
}: CustomsStepProps) {
  const router = useRouter();
  const [completing, setCompleting] = useState(false);
  const [skipping, setSkipping] = useState(false);
  const [autofillSuggestions, setAutofillSuggestions] = useState<
    CustomsAutofillSuggestion[]
  >([]);
  const [autofillDismissed, setAutofillDismissed] = useState(false);
  const [selectedRowId, setSelectedRowId] = useState<string | null>(null);
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const [bulkAcceptPending, startBulkAccept] = useTransition();

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

  const supplierByQuoteItemId = useSupplierByQuoteItemId(items);

  const customsNotes = ext<{ customs_notes?: string | null }>(quote).customs_notes ?? "";

  // Load autofill suggestions once per quote change. Fires-and-forget; silent
  // on error so customs workflow is never blocked by the suggestion endpoint.
  useEffect(() => {
    let cancelled = false;
    if (!isPendingCustoms || items.length === 0) {
      setAutofillSuggestions([]);
      return;
    }
    const payload = {
      items: items
        .filter((it) => it.brand && it.product_code)
        .map((it) => ({
          id: it.id,
          brand: it.brand,
          product_code: it.product_code,
        })),
    };
    if (payload.items.length === 0) {
      setAutofillSuggestions([]);
      return;
    }
    fetch("/api/customs/autofill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((r) => r.json())
      .then((json) => {
        if (cancelled) return;
        const list: CustomsAutofillSuggestion[] =
          json?.data?.suggestions ?? [];
        // Only surface suggestions for items that don't yet have hs_code.
        const targetIds = new Set(
          items.filter((it) => !ext<{ hs_code?: string | null }>(it).hs_code).map((it) => it.id),
        );
        setAutofillSuggestions(list.filter((s) => targetIds.has(s.item_id)));
      })
      .catch(() => {
        if (!cancelled) setAutofillSuggestions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [items, isPendingCustoms]);

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

  const handleBulkAccept = useCallback(
    (suggestions: CustomsAutofillSuggestion[]) => {
      startBulkAccept(async () => {
        try {
          const payload = {
            items: suggestions.map((s) => ({
              id: s.item_id,
              hs_code: s.hs_code,
              customs_duty: s.customs_duty ?? 0,
              license_ds_required: Boolean(s.license_ds_required),
              license_ss_required: Boolean(s.license_ss_required),
              license_sgr_required: Boolean(s.license_sgr_required),
              license_ds_cost: s.license_ds_cost ?? 0,
              license_ss_cost: s.license_ss_cost ?? 0,
              license_sgr_cost: s.license_sgr_cost ?? 0,
            })),
          };
          const res = await fetch(
            `/api/customs/${quote.id}/items/bulk`,
            {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(payload),
            },
          );
          const json = await res.json();
          if (!json?.success) {
            throw new Error(json?.error ?? "Не удалось применить");
          }
          toast.success(
            `Применено ${suggestions.length} предложений из истории`,
          );
          setAutofillSuggestions([]);
          router.refresh();
        } catch (err) {
          toast.error(
            err instanceof Error ? err.message : "Не удалось применить",
          );
        }
      });
    },
    [quote.id, router],
  );

  const selectedItem = useMemo(
    () => items.find((it) => it.id === selectedRowId) ?? null,
    [items, selectedRowId],
  );
  const selectedItemLabel = useMemo(() => {
    if (!selectedItem) return "";
    const parts: string[] = [];
    if (selectedItem.brand) parts.push(selectedItem.brand);
    if (selectedItem.product_code) parts.push(selectedItem.product_code);
    return parts.join(" · ") || selectedItem.product_name || "";
  }, [selectedItem]);

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
        {autofillSuggestions.length > 0 && !autofillDismissed && (
          <AutofillBanner
            totalItems={items.length}
            suggestions={autofillSuggestions}
            onAcceptAll={handleBulkAccept}
            onDismiss={() => setAutofillDismissed(true)}
            pending={bulkAcceptPending}
          />
        )}

        <CustomsItemsEditor
          items={items}
          invoiceCountryMap={invoiceCountryMap}
          supplierByQuoteItemId={supplierByQuoteItemId}
          userRoles={userRoles}
          autofillSuggestions={autofillSuggestions}
          onSelectRow={setSelectedRowId}
          onExpandRow={setExpandedRowId}
        />

        {selectedItem && (
          <ItemCustomsExpenses
            quoteId={quote.id}
            quoteItemId={selectedItem.id}
            itemLabel={selectedItemLabel}
            userRoles={userRoles}
          />
        )}

        <QuoteCustomsExpenses quoteId={quote.id} userRoles={userRoles} />

        <CustomsExpenses quoteId={quote.id} />

        <CustomsNotes quoteId={quote.id} initialNotes={customsNotes} />

        {userId && (
          <EntityNotesPanel
            entityType="quote"
            entityId={quote.id}
            initialNotes={quoteNotes}
            currentUser={{ id: userId, roles: userRoles }}
            title="Заметки таможни по КП"
            defaultVisibleTo={["customs", "head_of_customs", "sales", "procurement"]}
          />
        )}

        <CustomsInfoBlock quoteId={quote.id} orgId={quote.organization_id} />
      </div>

      <CustomsItemDialog
        open={expandedRowId !== null}
        onOpenChange={(next) => {
          if (!next) setExpandedRowId(null);
        }}
        quoteId={quote.id}
        item={items.find((it) => it.id === expandedRowId) ?? null}
        userRoles={userRoles}
        onSaved={() => router.refresh()}
      />
    </div>
  );
}
