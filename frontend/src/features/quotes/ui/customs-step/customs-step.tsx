"use client";

import { useCallback, useEffect, useMemo, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { completeCustoms, skipCustoms } from "@/entities/quote/mutations";
import type {
  QuoteDetailRow,
  QuoteItemRow,
  QuoteInvoiceRow,
} from "@/entities/quote/queries";
import { createClient } from "@/shared/lib/supabase/client";
import { ALTA_FEATURES_ENABLED } from "@/shared/lib/feature-flags";
import {
  AutofillBanner,
  type CustomsAutofillSuggestion,
} from "@/features/customs-autofill";
import {
  CertificatesSection,
  type QuoteItemForSelect,
} from "@/features/customs-certificates";
import { fetchOksmCountries } from "@/features/customs-country-dropdown";
import type { TableView } from "@/entities/table-view";
import { fetchAllAvailable } from "@/entities/table-view";
import {
  TableViewsDropdown,
  type DropdownTableView,
} from "@/features/table-views";
import { CustomsActionBar } from "./customs-action-bar";
import { CustomsItemsEditor } from "./customs-items-editor";
import {
  CUSTOMS_AVAILABLE_COLUMNS,
  CUSTOMS_TABLE_KEY,
} from "./customs-columns";
import { CUSTOMS_SYSTEM_VIEWS } from "./customs-views";
import { EntityNotesPanel } from "@/entities/entity-note";
import type { EntityNoteCardData } from "@/entities/entity-note/ui/entity-note-card";
import { CustomsInfoBlock } from "./customs-info-block";
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
  /** Table views available to the user (personal + org-shared). */
  tableViews?: readonly TableView[];
  /** True when the acting user may create/edit org-shared views. */
  canCreateSharedView?: boolean;
}

/**
 * Adapt the synthetic, client-side `CUSTOMS_SYSTEM_VIEWS` constants
 * (`SystemView` shape) to the `DropdownTableView` shape consumed by
 * `<TableViewsDropdown>`. The dropdown uses `is_system: true` to render
 * the «Системные» group above personal/shared rows (REQ-11 AC#4).
 *
 * The synthetic ids (`system:*`) cannot collide with UUID rows in
 * `kvota.user_table_views`, so the merged list is safe to feed straight
 * into the dropdown's `views` prop — see `customs-views.ts` for ID
 * scheme rationale.
 */
const CUSTOMS_SYSTEM_DROPDOWN_VIEWS: readonly DropdownTableView[] =
  CUSTOMS_SYSTEM_VIEWS.map((sv) => ({
    id: sv.id,
    userId: "system",
    tableKey: CUSTOMS_TABLE_KEY,
    name: sv.label,
    filters: {},
    sort: null,
    visibleColumns: sv.visibleColumnIds,
    isShared: false,
    organizationId: null,
    isDefault: false,
    createdAt: "1970-01-01T00:00:00.000Z",
    updatedAt: "1970-01-01T00:00:00.000Z",
    is_system: true,
  }));

export function CustomsStep({
  quote,
  items,
  invoices,
  userRoles,
  userId,
  quoteNotes = [],
  tableViews = [],
  canCreateSharedView = false,
}: CustomsStepProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [completing, setCompleting] = useState(false);
  const [skipping, setSkipping] = useState(false);
  const [autofillSuggestions, setAutofillSuggestions] = useState<
    CustomsAutofillSuggestion[]
  >([]);
  const [autofillDismissed, setAutofillDismissed] = useState(false);
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const [bulkAcceptPending, startBulkAccept] = useTransition();

  // Row 10 — OKSM country reference for the «Страна происх.» column.
  // Fetched once on mount; `kvota.countries` is small (~250 rows) and
  // stable. The resulting `Map<oksm_digital, name_ru>` is passed to the
  // Handsontable so the read-only column renders `Китай` instead of
  // the raw OKSM digit `156`. Edits still flow through the dialog's
  // `<CustomsCountryDropdown>` (separate fetch, small duplication OK).
  const [oksmNameMap, setOksmNameMap] = useState<Map<number, string>>(
    new Map()
  );
  useEffect(() => {
    let cancelled = false;
    fetchOksmCountries()
      .then((countries) => {
        if (cancelled) return;
        const map = new Map<number, string>();
        for (const c of countries) {
          map.set(c.oksm_digital, c.name_ru);
        }
        setOksmNameMap(map);
      })
      .catch((err) => {
        // Silent — the column falls back to the raw OKSM digit on miss,
        // which is the pre-fix behavior. Better than blocking the panel.
        console.error("Failed to load OKSM countries reference:", err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Row 8 — optimistic patch map for the dialog↔table sync. When the
  // HoT inline duty-mode chip fires `handleDutyModeChange`, the actual
  // server round-trip is async; opening the dialog before
  // `router.refresh()` completes would reseed the form from stale
  // `items`. We keep a synchronous local patch keyed by row id; merge
  // into the dialog's item; clear when fresh server data arrives.
  const [itemsOverride, setItemsOverride] = useState<
    Map<string, Partial<QuoteItemRow>>
  >(new Map());

  const patchItem = useCallback(
    (rowId: string, patch: Partial<QuoteItemRow>) => {
      setItemsOverride((prev) => {
        const next = new Map(prev);
        const existing = next.get(rowId) ?? {};
        next.set(rowId, { ...existing, ...patch });
        return next;
      });
    },
    []
  );

  // When the server returns fresh items (after router.refresh propagates
  // through the parent server component), clear any overrides whose data
  // is now reflected in the canonical row. We use a coarse "items prop
  // changed" signal — any new items array means refresh happened, so
  // drop the override map entirely.
  useEffect(() => {
    setItemsOverride((prev) => (prev.size === 0 ? prev : new Map()));
  }, [items]);

  // Views are seeded from server props and refreshed client-side after the
  // settings dialog mutates them. Keep them in state so a refresh after
  // save reflects immediately without a full router.refresh() round-trip.
  const [views, setViews] = useState<readonly TableView[]>(tableViews);
  useEffect(() => {
    setViews(tableViews);
  }, [tableViews]);

  // Merge the 4 synthetic system views in front of the user/org rows so
  // the dropdown renders «Системные» above «Личные»/«Общие» and the
  // `system:*` ids resolve via the same `views.find(...)` path used for
  // UUID rows. The system constants live as readonly module-level data
  // (`CUSTOMS_SYSTEM_DROPDOWN_VIEWS`); the `views` state still holds only
  // the real `TableView` rows so settings-dialog mutations don't have to
  // skip system rows.
  const dropdownViews = useMemo<readonly DropdownTableView[]>(
    () => [...CUSTOMS_SYSTEM_DROPDOWN_VIEWS, ...views],
    [views]
  );

  // Active view: either the `?customs_view=<id>` query param or the user's
  // default view. `null` means "show all columns".
  const viewParam = searchParams?.get("customs_view") ?? null;
  const defaultView = useMemo(
    () => views.find((v) => v.isDefault && !v.isShared) ?? null,
    [views]
  );
  const activeViewId = viewParam ?? defaultView?.id ?? null;
  const activeView = useMemo(
    () => dropdownViews.find((v) => v.id === activeViewId) ?? null,
    [dropdownViews, activeViewId]
  );
  const visibleColumns = activeView?.visibleColumns;

  const handleViewChange = useCallback(
    (nextViewId: string | null) => {
      const params = new URLSearchParams(searchParams?.toString() ?? "");
      if (nextViewId) {
        params.set("customs_view", nextViewId);
      } else {
        params.delete("customs_view");
      }
      // Preserve hash + pathname; push so back-button restores the previous view.
      const query = params.toString();
      router.push(query ? `?${query}` : "?", { scroll: false });
    },
    [router, searchParams]
  );

  const handleViewsRefresh = useCallback(async () => {
    if (!userId || !quote.organization_id) return;
    try {
      const next = await fetchAllAvailable(
        quote.organization_id,
        CUSTOMS_TABLE_KEY,
        userId
      );
      setViews(next);
    } catch (err) {
      console.error("Failed to refresh customs views:", err);
    }
  }, [userId, quote.organization_id]);

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

  // Items merged with any pending optimistic patches (Row 8). The dialog
  // reads from this so a chip-mode flip in HoT is reflected immediately
  // when the user opens the row card. HoT itself reads from `items`
  // (its internal HoT state already has the mirrored value via
  // setDataAtRowProp in handleDutyModeChange).
  const mergedItems = useMemo<QuoteItemRow[]>(() => {
    if (itemsOverride.size === 0) return items;
    return items.map((it) => {
      const patch = itemsOverride.get(it.id);
      return patch ? ({ ...it, ...patch } as QuoteItemRow) : it;
    });
  }, [items, itemsOverride]);

  // Load autofill suggestions once per quote change. Fires-and-forget; silent
  // on error so customs workflow is never blocked by the suggestion endpoint.
  // Gated by ALTA_FEATURES_ENABLED — when off, no fetch fires and suggestions
  // stay empty (which also clears the customs-autofill-row highlight via the
  // empty array propagating into <CustomsHandsontable>).
  useEffect(() => {
    if (!ALTA_FEATURES_ENABLED) {
      setAutofillSuggestions([]);
      return;
    }
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
          console.error("customs bulk autofill apply failed", {
            quoteId: quote.id,
            count: suggestions.length,
            err,
          });
          toast.error(
            err instanceof Error ? err.message : "Не удалось применить",
          );
        }
      });
    },
    [quote.id, router],
  );

  // ── CertificatesSection wiring (Phase B Wave 4 Task 9) ─────────────────
  // Map QuoteItemRow → QuoteItemForSelect for the certificates feature.
  // `rub_basis` is the proportional weight used by the cost-split helper;
  // for the section's «N из M позиций» counter only `items.length` matters,
  // but we feed a sane number here so the nested CertificateModal /
  // ExpenseModal multi-select preview remains accurate. The cost-split is
  // also recomputed server-side, so this client value is informational.
  const quoteItemsForCerts = useMemo<QuoteItemForSelect[]>(
    () =>
      items.map((it) => {
        const proforma = Number(
          ext<{ proforma_amount_excl_vat?: number | null }>(it)
            .proforma_amount_excl_vat ?? 0,
        );
        const quantity = Number(it.quantity ?? 0);
        return {
          id: it.id,
          position: Number(it.position ?? 0),
          name: it.product_name ?? "",
          product_code: it.product_code ?? null,
          // Best-effort RUB basis for the live-preview math inside the
          // cert/expense modals. Authoritative basis is computed server-side.
          rub_basis: proforma * (quantity || 1),
        };
      }),
    [items],
  );

  // Write gate mirrors `_CUSTOMS_ROLES` in `api/customs.py` — the server
  // also enforces this set, so the UI gate is purely cosmetic (read-only
  // consumers still see the data, mutations 403 server-side).
  const canEditCustoms = useMemo(
    () =>
      userRoles.some(
        (r) =>
          r === "customs" ||
          r === "head_of_customs" ||
          r === "head_of_logistics" || // dual-hat: logistics lead also handles customs in this org
          r === "admin",
      ),
    [userRoles],
  );

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
        {ALTA_FEATURES_ENABLED &&
          autofillSuggestions.length > 0 &&
          !autofillDismissed && (
            <AutofillBanner
              totalItems={items.length}
              suggestions={autofillSuggestions}
              onAcceptAll={handleBulkAccept}
              onDismiss={() => setAutofillDismissed(true)}
              pending={bulkAcceptPending}
            />
          )}

        {userId && quote.organization_id && (
          <div className="flex items-center justify-end">
            <TableViewsDropdown
              views={dropdownViews}
              activeViewId={activeViewId}
              onViewChange={handleViewChange}
              onViewsRefresh={handleViewsRefresh}
              tableKey={CUSTOMS_TABLE_KEY}
              availableColumns={CUSTOMS_AVAILABLE_COLUMNS}
              userId={userId}
              orgId={quote.organization_id}
              canCreateShared={canCreateSharedView}
            />
          </div>
        )}

        <CustomsItemsEditor
          items={items}
          invoiceCountryMap={invoiceCountryMap}
          supplierByQuoteItemId={supplierByQuoteItemId}
          userRoles={userRoles}
          autofillSuggestions={autofillSuggestions}
          onExpandRow={setExpandedRowId}
          visibleColumns={visibleColumns}
          oksmNameMap={oksmNameMap}
          onItemPatched={patchItem}
        />

        {/*
          Phase B Wave 4 Task 9 (REQ-6): unified «Расходы по таможне» section
          replaces the Phase A `<QuoteCustomsExpenses />` (per-quote) +
          `<ItemCustomsExpenses />` (per-item) split. Both data layers are
          now stored in `kvota.quote_certificates` with `is_custom_expense`
          discriminating between certificates and ad-hoc fees. The two
          Phase A components were deleted in 2026-05 (FB-260511-212235-0384
          cleanup) alongside the `license_*_cost` ghost-column removal.
        */}
        <CertificatesSection
          quoteId={quote.id}
          items={quoteItemsForCerts}
          canEdit={canEditCustoms}
        />

        {userId && (
          <EntityNotesPanel
            entityType="quote"
            entityId={quote.id}
            initialNotes={quoteNotes}
            currentUser={{ id: userId, roles: userRoles }}
            title="Заметки таможни по КП"
            defaultVisibleTo={["customs", "head_of_customs", "head_of_logistics", "sales", "procurement"]}
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
        // Row 8 fix — use `mergedItems` so in-flight optimistic patches
        // from HoT inline edits (e.g. duty-mode chip) are visible to the
        // dialog before `router.refresh()` round-trips.
        item={mergedItems.find((it) => it.id === expandedRowId) ?? null}
        // Phase B Wave 5 cleanup — pass the full quote-items array so the
        // dialog's BindPopover after-attach preview / Сертификация section
        // can resolve sibling positions (REQ-8 AC#7 «derived RUB-суммы» across
        // all attachments). Internally the dialog adapts QuoteItemRow →
        // QuoteItemForSelect; if omitted, the popover falls back to a
        // singleton list of just the current item.
        allItems={mergedItems}
        userRoles={userRoles}
        onSaved={() => router.refresh()}
      />
    </div>
  );
}
