"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, ChevronDown, ChevronRight, Download, Loader2, Mail, Package, Paperclip, Plus, Trash2, Undo2, Weight } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ProcurementItemsEditor } from "./procurement-items-editor";
import type { ProcurementEditorItem } from "./procurement-handsontable";
import { SendHistoryPanel } from "./send-history-panel";
import { ProcurementUnlockButton } from "./procurement-unlock-button";
import { LetterDraftComposer } from "./letter-draft-composer";
import { SplitInlineDialog } from "./split-inline-dialog";
import { MergeInlineDialog } from "./merge-inline-dialog";
import { AddCargoPlaceDialog } from "./add-cargo-place-dialog";
import { AddPositionsModal } from "./add-positions-modal";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";
import {
  completeInvoiceProcurement,
  deleteCargoPlace,
  deleteInvoice,
  fetchCargoPlaces,
  undoMerge,
  undoSplit,
  updateCargoPlace,
} from "@/entities/quote/mutations";
import {
  notifyInvoiceCompletedForKanban,
  notifyInvoiceSentForKanban,
} from "@/entities/quote/server-actions";
import { SUBSTATUS_LABELS_RU } from "@/shared/lib/workflow-substates";
import { INCOTERMS_2020 } from "@/shared/lib/incoterms";
import { SUPPORTED_CURRENCIES } from "@/shared/lib/currencies";
import { downloadInvoiceXls, markInvoiceSent } from "@/entities/invoice/mutations";
import { createClient } from "@/shared/lib/supabase/client";
import { extractErrorMessage } from "@/shared/lib/errors";
import { CityAutocomplete, CountryCombobox, findCountryByCode } from "@/shared/ui/geo";

type InvoiceExtras = {
  invoice_file_url?: string | null;
};

function ext<T>(row: unknown): T {
  return row as T;
}

const numberFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const INVOICE_STATUS_LABELS: Record<string, string> = {
  pending_procurement: "Ожидает закупки",
  pending_logistics: "Ожидает логистики",
  pending_customs: "Ожидает таможни",
  completed: "Завершён",
};

/**
 * Phase 5c: supplier-side positions. Sourced from kvota.invoice_items,
 * not quote_items. Each row represents one line in the supplier's КП and
 * may diverge from the customer's original quote_item via split/merge.
 *
 * Phase 5d Group 5 Appendix: aliased to `ProcurementEditorItem` — the same
 * shape is forwarded unchanged to procurement-handsontable, which binds
 * its COLUMN_KEYS to these invoice_items fields. Single source of truth
 * (procurement-handsontable) prevents drift between invoice-card's fetch
 * shape and the editor's expected row shape.
 */
export type InvoiceItemRow = ProcurementEditorItem;

/**
 * Minimal quote stub used for edit-gate computation. Parent may pass a full
 * QuoteDetailRow — any superset with these fields works. `items` stays as
 * QuoteItemRow[] because sibling editors (LetterDraftComposer, XLS export)
 * still read customer-side fields from it. ProcurementItemsEditor, however,
 * receives the supplier-side `invoiceItems` (post Phase 5d Group 5 Appendix).
 */
export interface InvoiceCardQuoteStub {
  procurement_completed_at: string | null;
}

interface InvoiceCardProps {
  invoice: QuoteInvoiceRow;
  /**
   * Customer-side quote_items of the quote this invoice belongs to.
   * Used by downstream editors that still render customer fields.
   */
  items: QuoteItemRow[];
  /**
   * Quote metadata needed for the edit-gate. Replaces the Phase 4a
   * `procurementCompleted: boolean` prop — now derived from the quote
   * itself so sibling code (unlock-request) can read the same source.
   */
  quote: InvoiceCardQuoteStub;
  /**
   * Optional pre-fetched invoice_items for this invoice. When omitted,
   * the card fetches them on mount. Tests and storybook pass in fixtures.
   */
  invoiceItems?: InvoiceItemRow[];
  /**
   * Optional pre-computed coverage summary per invoice_item. Format:
   *   - split:  "→ болт ×1 + шайба ×2"
   *   - merge:  "← болт, гайка, шайба объединены"
   *   - 1:1:    absent from map (no label rendered)
   */
  coverageSummaryByItem?: Record<string, string>;
  defaultExpanded?: boolean;
  userRoles?: string[];
  /**
   * Counter bumped by the parent (procurement-step) when an external
   * mutation invalidates the supplier-side positions fetched by this card.
   * Today's only trigger is «Назначить в КП» from QuotePositionsList — a
   * sibling component that can't reach this card's local refreshKey, so
   * the parent forwards a refresh signal via prop instead. Including it in
   * the load() effect's dep array forces a re-fetch of invoice_items +
   * coverage labels + sales-side join, mirroring the onMutated path used
   * by procurement-handsontable mutations.
   */
  externalRefreshKey?: number;
}

const numberFmtInline = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function InvoiceCard({
  invoice,
  items,
  // `quote` is no longer the source of procurement-completion truth (each
  // invoice has its own flag now). Kept in props for backward compat with
  // tests + the parent procurement-step.tsx, but unused inside the card.
  quote: _quote,
  invoiceItems: invoiceItemsOverride,
  coverageSummaryByItem: coverageOverride,
  defaultExpanded = false,
  userRoles = [],
  externalRefreshKey = 0,
}: InvoiceCardProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [unassigning, setUnassigning] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [downloadingXls, setDownloadingXls] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [language, setLanguage] = useState<"ru" | "en">("ru");
  // State shape mirrors what fetchCargoPlaces returns from
  // kvota.invoice_cargo_places (full row incl. id/invoice_id/created_at,
  // nullable dimension fields). Narrowing to a form-only shape here was
  // the root of TS2345 setter-type-mismatches across this file.
  const [cargoPlaces, setCargoPlaces] = useState<
    Awaited<ReturnType<typeof fetchCargoPlaces>>
  >([]);
  // Invoice-level deferred-fill fields. Initial values from the `invoice`
  // prop; saves go through `updateInvoice` on blur (text/number) or
  // change (selects). Local state survives in-flight saves so failures
  // don't blank the user's input.
  const [pickupCityLocal, setPickupCityLocal] = useState(invoice.pickup_city ?? "");
  const [pickupCountryCodeLocal, setPickupCountryCodeLocal] = useState<string | null>(
    invoice.pickup_country_code ?? null
  );
  const [incotermsLocal, setIncotermsLocal] = useState(invoice.supplier_incoterms ?? "");
  const [currencyLocal, setCurrencyLocal] = useState(invoice.currency ?? "USD");
  const [vatRateLocal, setVatRateLocal] = useState(
    (invoice as { vat_rate?: number | null }).vat_rate != null
      ? String((invoice as { vat_rate?: number | null }).vat_rate)
      : ""
  );
  const [fetchedInvoiceItems, setFetchedInvoiceItems] = useState<
    InvoiceItemRow[]
  >([]);
  const [fetchedCoverage, setFetchedCoverage] = useState<Record<string, string>>({});
  // Sales-side columns (product_code, product_name, name_en) joined from
  // the linked quote_items via invoice_item_coverage. Read-only in the
  // procurement handsontable; let the procurement manager see what sales
  // recorded alongside their own supplier-side fields.
  // `name_en` propagates to the letter-draft composer so EN-language
  // letters render translated position names when sales has filled it
  // (РОЗ-117 / МОЗ-104). The XLS export already reads `name_en` via the
  // same coverage join in services/xls_export_service.py.
  const [salesByItemId, setSalesByItemId] = useState<
    Record<
      string,
      {
        product_code: string;
        product_name: string;
        unit: string;
        name_en: string | null;
      }
    >
  >({});
  const [invoiceItemsLoading, setInvoiceItemsLoading] = useState(
    invoiceItemsOverride === undefined
  );
  // 1:1-covered quote_items in THIS invoice — candidates for Split/Merge.
  // A quote_item is 1:1-covered when it has exactly one invoice_item in this
  // invoice covering it AND that invoice_item covers only this quote_item
  // AND the ratio is 1. Items already part of a split/merge are excluded
  // from both modals to prevent chain-structural changes.
  const [oneToOneCandidates, setOneToOneCandidates] = useState<
    Array<{ id: string; product_name: string; quantity: number }>
  >([]);
  // Per-row split eligibility, keyed by invoice_item.id. Same 1:1 condition
  // as oneToOneCandidates, but indexed for O(1) lookup from the handsontable
  // row renderer (which only knows the invoice_item.id, not the source qi).
  const [splitableByItemId, setSplitableByItemId] = useState<
    Record<
      string,
      {
        sourceQuoteItemId: string;
        sourceQuantity: number;
        sourceProductName: string;
      }
    >
  >({});
  // Per-row "this is a split child" info, keyed by invoice_item.id. Drives
  // the inline ↪ undo-split icon. Set when the row's source quote_item is
  // covered by ≥2 invoice_items in this invoice.
  const [splitChildByItemId, setSplitChildByItemId] = useState<
    Record<string, { sourceQuoteItemId: string; sourceProductName: string }>
  >({});
  // Per-row merge eligibility, keyed by invoice_item.id. Same 1:1 condition
  // as splitableByItemId, BUT only populated when the invoice has ≥ 2 such
  // candidates total — a single 1:1 row has nobody to merge with, so the
  // ⋃ icon stays hidden. Carries source-qi metadata so the dialog can
  // resolve partners without re-querying.
  const [mergeableByItemId, setMergeableByItemId] = useState<
    Record<
      string,
      {
        sourceQuoteItemId: string;
        sourceProductName: string;
        sourceQuantity: number;
      }
    >
  >({});
  // Per-row "this is a merge result" info, keyed by invoice_item.id. Drives
  // the inline ↩ undo-merge icon. Set when this invoice_item covers ≥ 2
  // quote_items (the canonical merge state).
  const [mergeResultByItemId, setMergeResultByItemId] = useState<
    Record<string, true>
  >({});
  // Bumped after structural ops (split, merge) so the load() effect re-runs
  // even though invoice.id is stable. Without this, splitableByItemId stays
  // stale and the split icon may surface on rows that are no longer 1:1 —
  // causing a confusing "split didn't work" toast on the second attempt.
  const [refreshKey, setRefreshKey] = useState(0);
  const [splitInlineState, setSplitInlineState] = useState<{
    invoiceItemId: string;
    sourceQuoteItemId: string;
    sourceQuantity: number;
    sourceProductName: string;
    defaults: {
      product_name: string;
      brand: string;
      supplier_sku: string;
      purchase_price_original: number | null;
    };
  } | null>(null);
  const [mergeInlineState, setMergeInlineState] = useState<{
    initiatorInvoiceItemId: string;
    initiatorSourceQuoteItemId: string;
    defaults: {
      product_name: string;
      brand: string;
      supplier_sku: string;
      purchase_price_original: number | null;
    };
  } | null>(null);
  const [addPositionsOpen, setAddPositionsOpen] = useState(false);
  const [addCargoOpen, setAddCargoOpen] = useState(false);
  // Confirmation dialog gating «Завершить закупку». Stage transition is hard
  // to undo (locks the КП for editing, advances kanban) — explicit confirm
  // prevents accidental clicks. `completing` blocks double-submit while the
  // mutation is in flight.
  const [completeConfirmOpen, setCompleteConfirmOpen] = useState(false);
  const [completing, setCompleting] = useState(false);

  // Procurement completion now lives PER invoice (migration 298). Reading
  // off `quote.procurement_completed_at` was the legacy behaviour — kept
  // as a fallback for any unmigrated rows but ignored once the new column
  // is populated, so the new field always wins when set.
  const invoiceProcurementCompletedAt =
    (invoice as { procurement_completed_at?: string | null })
      .procurement_completed_at ?? null;
  const procurementCompleted = invoiceProcurementCompletedAt != null;
  const invoiceItems = invoiceItemsOverride ?? fetchedInvoiceItems;
  const coverageSummaryByItem = coverageOverride ?? fetchedCoverage;
  const isEmpty = invoiceItems.length === 0;
  // Phase 5c: edit-gate decoupled from sent_at. Locking is procurement-stage
  // completion; a sent-but-not-completed invoice is still editable.
  const isLocked = procurementCompleted;
  const canSend =
    invoiceItems.length > 0 &&
    (userRoles.includes("admin") ||
      userRoles.includes("procurement") ||
      userRoles.includes("head_of_procurement") ||
      userRoles.includes("procurement_senior"));

  useEffect(() => {
    fetchCargoPlaces(invoice.id).then(setCargoPlaces);
  }, [invoice.id]);

  useEffect(() => {
    if (invoiceItemsOverride !== undefined) return;
    const supabase = createClient();

    let cancelled = false;
    async function load() {
      setInvoiceItemsLoading(true);
      try {
        const { data: ii } = await supabase
          .from("invoice_items")
          .select(
            "id, invoice_id, position, product_name, supplier_sku, brand, quantity, purchase_price_original, purchase_currency, minimum_order_quantity, production_time_days, weight_in_kg, dimension_height_mm, dimension_width_mm, dimension_length_mm"
          )
          .eq("invoice_id", invoice.id)
          .order("position", { ascending: true });
        if (cancelled) return;
        const rows = (ii ?? []) as InvoiceItemRow[];
        setFetchedInvoiceItems(rows);

        if (rows.length === 0) {
          setFetchedCoverage({});
          setSalesByItemId({});
          setSplitableByItemId({});
          setSplitChildByItemId({});
          setMergeableByItemId({});
          setMergeResultByItemId({});
          return;
        }

        // Coverage summary: for each invoice_item, fetch its coverage rows
        // (and sibling coverage for merge detection). Labels:
        //   split  = 1 quote_item → N invoice_items → "→ A ×1 + B ×2"
        //   merge  = N quote_items → 1 invoice_item → "← A, B, C объединены"
        //   1:1    = no entry in map
        // Step 1: pull coverage rows (FK pairs only — no embed). Embed via
        // PostgREST has been flaky in this stack with multi-field selects;
        // a plain join + separate quote_items fetch is more robust.
        const { data: cov } = await supabase
          .from("invoice_item_coverage")
          .select("invoice_item_id, quote_item_id, ratio")
          .in(
            "invoice_item_id",
            rows.map((r) => r.id)
          );

        // Step 2: fetch the quote_items referenced by the coverage rows.
        // product_code and product_name fuel the read-only sales-side
        // columns in the procurement handsontable; product_name + quantity
        // also drive the split/merge coverage label below. `name_en` is
        // forwarded to the letter-draft composer so EN-language letters
        // render the translated position name when sales has filled it
        // (РОЗ-117 / МОЗ-104 — without this, EN letters fell back to the
        // Russian product_name silently).
        const referencedQiIds = Array.from(
          new Set(
            (cov ?? []).map((r) => (r as { quote_item_id: string }).quote_item_id)
          )
        );
        const qiById = new Map<
          string,
          {
            product_code: string | null;
            product_name: string;
            quantity: number;
            unit: string | null;
            name_en: string | null;
          }
        >();
        if (referencedQiIds.length > 0) {
          const { data: qis } = await supabase
            .from("quote_items")
            .select("id, product_code, product_name, quantity, unit, name_en")
            .in("id", referencedQiIds);
          for (const qi of (qis ?? []) as Array<{
            id: string;
            product_code: string | null;
            product_name: string;
            quantity: number;
            unit: string | null;
            name_en: string | null;
          }>) {
            qiById.set(qi.id, {
              product_code: qi.product_code,
              product_name: qi.product_name,
              quantity: qi.quantity,
              unit: qi.unit,
              name_en: qi.name_en,
            });
          }
        }

        const coverageByIi = new Map<
          string,
          Array<{
            quote_item_id: string;
            ratio: number;
            product_code: string;
            product_name: string;
            quantity: number;
            unit: string;
            name_en: string | null;
          }>
        >();
        const iiByQi = new Map<string, string[]>();
        for (const row of (cov ?? []) as unknown as Array<{
          invoice_item_id: string;
          quote_item_id: string;
          ratio: number;
        }>) {
          const qi = qiById.get(row.quote_item_id);
          const list = coverageByIi.get(row.invoice_item_id) ?? [];
          list.push({
            quote_item_id: row.quote_item_id,
            ratio: row.ratio,
            product_code: qi?.product_code ?? "",
            product_name: qi?.product_name ?? "",
            quantity: Number(qi?.quantity ?? 0),
            unit: qi?.unit ?? "",
            name_en: qi?.name_en ?? null,
          });
          coverageByIi.set(row.invoice_item_id, list);

          const iis = iiByQi.get(row.quote_item_id) ?? [];
          iis.push(row.invoice_item_id);
          iiByQi.set(row.quote_item_id, iis);
        }

        // Build sales-side display map: per invoice_item, join all linked
        // quote_items' product_code / product_name with " / " for the merge
        // case (N qi → 1 ii). Empty strings are skipped so we don't emit
        // " / " padding when one of the joined items has no product_code.
        // ``unit`` (Ед. Изм) is taken from the first covering quote_item —
        // merged rows must share unit by construction (validated elsewhere).
        // ``name_en`` follows the same join shape: NULLs are skipped so a
        // partially-translated merge still surfaces the parts that have a
        // translation; result is null only when no covering quote_item has
        // a translation set (composer falls back to product_name).
        const salesMap: Record<
          string,
          {
            product_code: string;
            product_name: string;
            unit: string;
            name_en: string | null;
          }
        > = {};
        for (const ii of rows) {
          const covers = coverageByIi.get(ii.id) ?? [];
          if (covers.length === 0) continue;
          const enParts = covers
            .map((c) => c.name_en)
            .filter((v): v is string => Boolean(v));
          salesMap[ii.id] = {
            product_code: covers
              .map((c) => c.product_code)
              .filter(Boolean)
              .join(" / "),
            product_name: covers
              .map((c) => c.product_name)
              .filter(Boolean)
              .join(" / "),
            unit: covers[0]?.unit ?? "",
            name_en: enParts.length > 0 ? enParts.join(" / ") : null,
          };
        }

        const summary: Record<string, string> = {};
        // 1:1 candidates: exactly one invoice_item covering only one
        // quote_item at ratio=1 (no split sibling, no merge partner).
        const candidates: Array<{
          id: string;
          product_name: string;
          quantity: number;
        }> = [];
        const splitable: Record<
          string,
          {
            sourceQuoteItemId: string;
            sourceQuantity: number;
            sourceProductName: string;
          }
        > = {};
        const splitChild: Record<
          string,
          { sourceQuoteItemId: string; sourceProductName: string }
        > = {};
        const mergeResult: Record<string, true> = {};
        const seenQi = new Set<string>();
        for (const ii of rows) {
          const covers = coverageByIi.get(ii.id) ?? [];
          if (covers.length > 1) {
            mergeResult[ii.id] = true;
            // Merge: 1 invoice_item covers ≥2 quote_items
            summary[ii.id] =
              "\u2190 " +
              covers.map((c) => c.product_name).join(", ") +
              " объединены";
            continue;
          }
          if (covers.length === 1) {
            const sourceQi = covers[0].quote_item_id;
            const siblings = iiByQi.get(sourceQi) ?? [];
            if (siblings.length >= 2) {
              // Split: 1 quote_item covered by ≥2 invoice_items
              const parts = siblings
                .map((sid) => {
                  const sii = rows.find((r) => r.id === sid);
                  const scov = coverageByIi.get(sid) ?? [];
                  const rat = scov.find((c) => c.quote_item_id === sourceQi)?.ratio ?? 1;
                  return sii ? `${sii.product_name} ×${rat}` : "";
                })
                .filter(Boolean);
              summary[ii.id] = "\u2192 " + parts.join(" + ");
              splitChild[ii.id] = {
                sourceQuoteItemId: sourceQi,
                sourceProductName: covers[0].product_name,
              };
            } else if (
              Number(covers[0].ratio) === 1 &&
              !seenQi.has(sourceQi)
            ) {
              // 1:1: candidate for both Split (source) and Merge (sibling)
              candidates.push({
                id: sourceQi,
                product_name: covers[0].product_name,
                quantity: covers[0].quantity,
              });
              splitable[ii.id] = {
                sourceQuoteItemId: sourceQi,
                sourceQuantity: covers[0].quantity,
                sourceProductName: covers[0].product_name,
              };
              seenQi.add(sourceQi);
            }
          }
        }
        // Merge eligibility: only if the invoice has ≥2 1:1 candidates,
        // i.e. a candidate has somebody else to merge with. Otherwise the
        // ⋃ icon stays hidden everywhere.
        const mergeable: Record<
          string,
          {
            sourceQuoteItemId: string;
            sourceProductName: string;
            sourceQuantity: number;
          }
        > = {};
        if (Object.keys(splitable).length >= 2) {
          for (const [iiId, meta] of Object.entries(splitable)) {
            mergeable[iiId] = {
              sourceQuoteItemId: meta.sourceQuoteItemId,
              sourceProductName: meta.sourceProductName,
              sourceQuantity: meta.sourceQuantity,
            };
          }
        }

        if (!cancelled) {
          setFetchedCoverage(summary);
          setSalesByItemId(salesMap);
          setOneToOneCandidates(candidates);
          setSplitableByItemId(splitable);
          setSplitChildByItemId(splitChild);
          setMergeableByItemId(mergeable);
          setMergeResultByItemId(mergeResult);
        }
      } finally {
        if (!cancelled) setInvoiceItemsLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [invoice.id, invoiceItemsOverride, refreshKey, externalRefreshKey]);

  const supplierName =
    (invoice.supplier as { name: string } | null)?.name ?? "\u2014";
  const buyerName =
    (invoice.buyer_company as { name: string; company_code: string } | null)?.name ?? null;
  const pickupCity = invoice.pickup_city ?? null;
  const pickupCountryCode = invoice.pickup_country_code ?? null;
  const pickupCountryRu = pickupCountryCode
    ? findCountryByCode(pickupCountryCode)?.nameRu ?? null
    : null;
  const pickupLocationLabel =
    pickupCity && pickupCountryRu && pickupCountryCode
      ? `${pickupCity}, ${pickupCountryRu} (${pickupCountryCode})`
      : pickupCity ??
        (pickupCountryRu && pickupCountryCode
          ? `${pickupCountryRu} (${pickupCountryCode})`
          : null);
  const supplierIncoterms = invoice.supplier_incoterms ?? null;
  // Phase 5c: totals come from invoice_items (supplier's own positions),
  // not quote_items. Merged invoice_items are counted once (that's the
  // point — a single row in the supplier КП).
  const totalAmount = invoiceItems.reduce((sum, item) => {
    const price = item.purchase_price_original ?? 0;
    return sum + price * item.quantity;
  }, 0);
  const currency = invoice.currency ?? "USD";
  const hasFile = ext<InvoiceExtras>(invoice).invoice_file_url != null;

  // Aggregations treat null (user-not-yet-filled) as 0 — matches the
  // pre-PR behavior when the state was narrowly typed as non-nullable.
  const cargoWeight = cargoPlaces.reduce(
    (sum, cp) => sum + (cp.weight_kg ?? 0),
    0
  );
  const cargoVolume = cargoPlaces.reduce(
    (sum, cp) =>
      sum + ((cp.length_mm ?? 0) * (cp.width_mm ?? 0) * (cp.height_mm ?? 0)) / 1e9,
    0
  );
  const hasCargoPlaces = cargoPlaces.length > 0;

  const hasInvoiceWeight = invoice.total_weight_kg != null || invoice.total_volume_m3 != null;

  // Generic save for the deferred-fill invoice-level fields. No-op when the
  // new value is identical to the current invoice prop (avoids spurious
  // PostgREST round-trips on blur of unchanged inputs).
  async function handleSaveInvoiceField(
    updates: Record<string, string | number | null>
  ) {
    try {
      const supabase = (await import("@/shared/lib/supabase/client")).createClient();
      const { error } = await supabase
        .from("invoices")
        .update(updates)
        .eq("id", invoice.id);
      if (error) throw error;
      toast.success("Сохранено");
      router.refresh();
    } catch (err) {
      console.error("[invoice-card] save invoice field failed:", err);
      toast.error(extractErrorMessage(err) ?? "Не удалось сохранить");
    }
  }

  async function handleDownloadXls() {
    setDownloadingXls(true);
    try {
      await downloadInvoiceXls(invoice.id, language);
      toast.success("XLS скачан");
      router.refresh();
    } catch (err) {
      console.error("[invoice-card] download XLS failed:", err);
      toast.error(extractErrorMessage(err) ?? "Не удалось скачать XLS");
    } finally {
      setDownloadingXls(false);
    }
  }

  async function handleUnassignAll() {
    setUnassigning(true);
    try {
      // Phase 5c: remove invoice_items + coverage (cascade) and clear any
      // composition pointers on quote_items that pointed here. Does not
      // touch alternative coverage in other invoices (non-destructive).
      const supabase = createClient();

      if (invoiceItems.length > 0) {
        const { error: delErr } = await supabase
          .from("invoice_items")
          .delete()
          .in(
            "id",
            invoiceItems.map((ii) => ii.id)
          );
        if (delErr) throw delErr;
      }

      const { error: ptrErr } = await supabase
        .from("quote_items")
        .update({ composition_selected_invoice_id: null })
        .eq("composition_selected_invoice_id", invoice.id);
      if (ptrErr) throw ptrErr;

      toast.success(
        `${invoiceItems.length} поз. возвращены в нераспределённые`
      );
      router.refresh();
    } catch (err) {
      console.error("[invoice-card] unassign all failed:", err);
      toast.error(extractErrorMessage(err) ?? "Не удалось убрать позиции из КП");
    } finally {
      setUnassigning(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteInvoice(invoice.id);
      toast.success(`Инвойс ${invoice.invoice_number} удалён`);
      router.refresh();
    } catch (err) {
      console.error("[invoice-card] delete invoice failed:", err);
      toast.error(extractErrorMessage(err) ?? "Не удалось удалить КП");
    } finally {
      setDeleting(false);
    }
  }

  async function handleCompleteProcurement() {
    setCompleting(true);
    try {
      await completeInvoiceProcurement(invoice.id);
      toast.success("Закупка по КП завершена");
      // Best-effort kanban advance for any brand-slice that's
      // now fully covered by completed invoices.
      try {
        const { advancedSlices } =
          await notifyInvoiceCompletedForKanban(invoice.id);
        for (const s of advancedSlices) {
          toast.info(
            `Карточка «${s.brand || "без бренда"}» автоматически переведена в «${SUBSTATUS_LABELS_RU[s.to as keyof typeof SUBSTATUS_LABELS_RU] ?? s.to}»`
          );
        }
      } catch (err) {
        console.error(
          "[invoice-card] kanban advance failed:",
          err
        );
      }
      setCompleteConfirmOpen(false);
      router.refresh();
      setRefreshKey((k) => k + 1);
    } catch (err) {
      console.error(
        "[invoice-card] complete procurement failed:",
        err
      );
      toast.error(
        extractErrorMessage(err) ?? "Не удалось завершить закупку"
      );
    } finally {
      setCompleting(false);
    }
  }

  // Guard: a КП with zero positions OR zero priced positions has nothing
  // to send to logistics — completing it would advance the workflow on an
  // empty record, which is the destructive footgun the QA bug reproduces.
  // Counts only non-null, strictly positive supplier prices.
  const positionsWithPriceCount = invoiceItems.reduce(
    (count, item) =>
      item.purchase_price_original != null && item.purchase_price_original > 0
        ? count + 1
        : count,
    0
  );
  const hasNoPositions = invoiceItems.length === 0;
  const hasNoPricedPositions = positionsWithPriceCount === 0;
  const cannotComplete = hasNoPositions || hasNoPricedPositions;

  const sentAt = invoice.sent_at;
  const hasSentAt = sentAt != null;

  return (
    <Card className="overflow-hidden" data-invoice-id={invoice.id}>
      <div className="flex items-center">
        <button
          type="button"
          onClick={() => setExpanded((prev) => !prev)}
          className="flex-1 px-4 py-3 flex items-center gap-3 text-left hover:bg-muted/50 transition-colors"
        >
          {expanded ? (
            <ChevronDown size={16} className="shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight size={16} className="shrink-0 text-muted-foreground" />
          )}

          <span className="font-medium text-sm truncate">
            {invoice.invoice_number}
          </span>

          <span className="text-sm text-muted-foreground truncate">
            {supplierName}
          </span>

          {buyerName && (
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">
              → {buyerName}
            </span>
          )}

          {/* Header chips below duplicate the editable form fields rendered in
              the «Параметры отгрузки» / «Грузовые места» sections when the
              card is expanded. Hide them on expand to avoid the «Часть не
              возможно прочесть» overflow + visual redundancy reported in
              МОЗ-94 / РОЗ-107/108. Collapsed state keeps them as preview. */}
          {!expanded && pickupLocationLabel && (
            <span
              data-testid="invoice-card-header-pickup-location"
              className="text-xs text-muted-foreground truncate hidden sm:inline"
            >
              {pickupLocationLabel}
            </span>
          )}

          {!expanded && supplierIncoterms && (
            <span
              data-testid="invoice-card-header-incoterms"
              className="text-xs text-muted-foreground truncate hidden sm:inline"
            >
              Условия: {supplierIncoterms}
            </span>
          )}

          {!expanded && hasInvoiceWeight && (
            <span
              data-testid="invoice-card-header-weight"
              className="text-xs text-muted-foreground tabular-nums shrink-0 hidden sm:inline"
            >
              {invoice.total_weight_kg != null && <>{numberFmt.format(invoice.total_weight_kg)}&nbsp;кг</>}
              {invoice.total_weight_kg != null && invoice.total_volume_m3 != null && " · "}
              {invoice.total_volume_m3 != null && <>{numberFmt.format(invoice.total_volume_m3)}&nbsp;м&sup3;</>}
            </span>
          )}

          {!expanded && hasCargoPlaces && (
            <span
              data-testid="invoice-card-header-cargo-summary"
              className="text-xs text-muted-foreground tabular-nums shrink-0 hidden sm:inline"
            >
              {cargoPlaces.length} мест &middot; {numberFmt.format(cargoWeight)} кг &middot; {cargoVolume.toFixed(2)} м&sup3;
            </span>
          )}

          <Badge variant="secondary" className="ml-auto shrink-0">
            {invoiceItems.length} поз.
          </Badge>

          <span className="text-sm font-mono tabular-nums shrink-0">
            {numberFmt.format(totalAmount)} {currency}
          </span>

          {invoice.status && (
            <Badge variant="outline" className="shrink-0">
              {INVOICE_STATUS_LABELS[invoice.status] ?? invoice.status}
            </Badge>
          )}

          {hasSentAt && (
            // Phase 5c: purely informational — NOT a lock indicator.
            // The edit-gate is driven by per-invoice procurement_completed_at.
            <Badge variant="default" className="shrink-0 text-xs bg-green-600">
              Отправлено {new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit" }).format(new Date(sentAt!))}
            </Badge>
          )}

          {procurementCompleted && invoiceProcurementCompletedAt && (
            <Badge
              variant="default"
              className="shrink-0 text-xs bg-blue-600 hover:bg-blue-600"
            >
              Закупка завершена{" "}
              {new Intl.DateTimeFormat("ru-RU", {
                day: "2-digit",
                month: "2-digit",
              }).format(new Date(invoiceProcurementCompletedAt))}
            </Badge>
          )}

          {hasFile && (
            <Paperclip size={14} className="shrink-0 text-muted-foreground" />
          )}
        </button>

        {isLocked ? (
          <div className="mr-2">
            <ProcurementUnlockButton invoiceId={invoice.id} />
          </div>
        ) : isEmpty ? (
          <div className="mr-2 flex items-center gap-1">
            <Button
              size="sm"
              className="bg-accent text-white hover:bg-accent-hover"
              onClick={() => setAddPositionsOpen(true)}
              title="Добавить позиции в КП поставщику"
            >
              <Plus size={14} className="mr-1" />
              Добавить позиции
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-destructive"
              onClick={handleDelete}
              disabled={deleting}
              title="Удалить пустое КП поставщику"
            >
              {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            </Button>
          </div>
        ) : (
          <div className="mr-2 flex items-center gap-0.5">
            {/* Both Split (↧) and Merge (⋃) live as per-row icons in the
                procurement handsontable below. Header buttons retired. */}
            {!hasSentAt && invoiceItems.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={async () => {
                  try {
                    await markInvoiceSent(invoice.id);
                    toast.success("КП отмечен отправленным");
                    try {
                      const { advancedSlices } =
                        await notifyInvoiceSentForKanban(invoice.id);
                      for (const s of advancedSlices) {
                        toast.info(
                          `Карточка «${s.brand || "без бренда"}» автоматически переведена в «${SUBSTATUS_LABELS_RU[s.to as keyof typeof SUBSTATUS_LABELS_RU] ?? s.to}»`
                        );
                      }
                    } catch (err) {
                      console.error(
                        "[invoice-card] kanban advance failed:",
                        err
                      );
                    }
                    router.refresh();
                  } catch (err) {
                    console.error(
                      "[invoice-card] markInvoiceSent failed:",
                      err
                    );
                    toast.error(
                      extractErrorMessage(err) ?? "Не удалось отметить отправленным"
                    );
                  }
                }}
                title="Пометить КП как отправленный поставщику. Позиции бренда в этом КП передвинутся на канбане в «Ожидание цен»."
              >
                <Mail size={14} className="mr-1" />
                Отправлено поставщику
              </Button>
            )}
            <Button
              variant="default"
              size="sm"
              className="bg-blue-600 text-white hover:bg-blue-700 text-xs"
              onClick={() => setCompleteConfirmOpen(true)}
              title="Закрыть закупку по этому КП и передать его в логистику / таможню"
            >
              <CheckCircle2 size={14} className="mr-1" />
              Завершить закупку
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-destructive"
              onClick={handleUnassignAll}
              disabled={unassigning}
              title="Вернуть все позиции в нераспределённые"
            >
              {unassigning ? <Loader2 size={14} className="animate-spin" /> : <Undo2 size={14} />}
            </Button>
          </div>
        )}
      </div>

      {expanded && (
        <div className="border-t border-border">
          {!procurementCompleted ? (
            <div className="px-4 py-3 bg-muted/30 border-b border-border space-y-3">
              <div className="flex items-center gap-2">
                <Weight size={14} className="text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">
                  Параметры отгрузки
                </span>
              </div>

              {/* Row: Country + City + Incoterms */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground">Страна отгрузки</span>
                  <CountryCombobox
                    value={pickupCountryCodeLocal}
                    onChange={(code) => {
                      if (code === pickupCountryCodeLocal) return;
                      setPickupCountryCodeLocal(code);
                      const ruName = code ? findCountryByCode(code)?.nameRu ?? null : null;
                      void handleSaveInvoiceField({
                        pickup_country_code: code,
                        pickup_country: ruName,
                      });
                    }}
                    placeholder="Выберите страну…"
                    ariaLabel="Страна отгрузки"
                  />
                </div>
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground">Город</span>
                  {/* Country-aware autocomplete with HERE-Geocode-backed
                      catalog (per shared/ui/geo). Without a country code
                      the input self-disables and asks the user to pick a
                      country first — which is the correct UX for shipping
                      origin. */}
                  <CityAutocomplete
                    value={pickupCityLocal}
                    countryCode={pickupCountryCodeLocal}
                    onChange={(next) => {
                      setPickupCityLocal(next);
                      const value = next.trim() === "" ? null : next;
                      if (value === (invoice.pickup_city ?? null)) return;
                      void handleSaveInvoiceField({ pickup_city: value });
                    }}
                    placeholder="Начните вводить город…"
                    ariaLabel="Город отгрузки"
                  />
                </div>
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground">Условия поставки</span>
                  <select
                    value={incotermsLocal}
                    onChange={(e) => {
                      const next = e.target.value;
                      setIncotermsLocal(next);
                      const value = next || null;
                      if (value === (invoice.supplier_incoterms ?? null)) return;
                      void handleSaveInvoiceField({ supplier_incoterms: value });
                    }}
                    className="w-full h-7 px-2 text-xs border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
                  >
                    <option value="">— не указано —</option>
                    {INCOTERMS_2020.map((term) => (
                      <option key={term.code} value={term.code}>
                        {term.code} — {term.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Row: Currency + VAT */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground">Валюта</span>
                  <select
                    value={currencyLocal}
                    onChange={(e) => {
                      const next = e.target.value;
                      setCurrencyLocal(next);
                      if (next === (invoice.currency ?? "USD")) return;
                      void handleSaveInvoiceField({ currency: next });
                    }}
                    className="w-full h-7 px-2 text-xs border border-input rounded-lg bg-transparent focus:outline-none focus:ring-2 focus:ring-ring/50 focus:border-ring"
                  >
                    {SUPPORTED_CURRENCIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <span className="text-xs text-muted-foreground">НДС, %</span>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    placeholder="НДС"
                    value={vatRateLocal}
                    onChange={(e) => setVatRateLocal(e.target.value)}
                    onBlur={() => {
                      const trimmed = vatRateLocal.trim();
                      const parsed = trimmed === "" ? null : parseFloat(trimmed);
                      if (parsed !== null && Number.isNaN(parsed)) return;
                      const current =
                        (invoice as { vat_rate?: number | null }).vat_rate ?? null;
                      if (parsed === current) return;
                      void handleSaveInvoiceField({ vat_rate: parsed });
                    }}
                    className="h-7 text-xs tabular-nums"
                  />
                </div>
              </div>
            </div>
          ) : hasInvoiceWeight ? (
            <div className="px-4 py-2 bg-muted/30 border-b border-border">
              <div className="flex items-center gap-2">
                <Weight size={14} className="text-muted-foreground" />
                <span className="text-xs text-muted-foreground tabular-nums">
                  {invoice.total_weight_kg != null && <>{numberFmt.format(invoice.total_weight_kg)} кг</>}
                  {invoice.total_weight_kg != null && invoice.total_volume_m3 != null && " · "}
                  {invoice.total_volume_m3 != null && <>{numberFmt.format(invoice.total_volume_m3)} м³</>}
                </span>
              </div>
            </div>
          ) : null}
          {!procurementCompleted ? (
            <div className="px-4 py-3 bg-muted/30 border-b border-border space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Package size={14} className="text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground">
                    Грузовые места ({cargoPlaces.length})
                  </span>
                  {cargoPlaces.length > 0 && (
                    <span className="text-xs text-muted-foreground tabular-nums">
                      · Σ{" "}
                      {numberFmt.format(
                        cargoPlaces.reduce(
                          (sum, cp) => sum + (cp.weight_kg ?? 0),
                          0
                        )
                      )}{" "}
                      кг
                    </span>
                  )}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-xs"
                  onClick={() => setAddCargoOpen(true)}
                >
                  <Plus size={14} />
                  Добавить место
                </Button>
              </div>
              {cargoPlaces.length === 0 ? (
                <p className="text-xs text-muted-foreground italic">
                  Грузовые места не указаны.
                </p>
              ) : (
                <div className="space-y-1.5">
                  {cargoPlaces.map((cp) => (
                    <div
                      key={cp.position}
                      className="flex items-center gap-2"
                    >
                      <span className="text-xs text-muted-foreground w-16 shrink-0">
                        Место {cp.position}
                      </span>
                      <Input
                        type="number"
                        step="0.01"
                        min="0"
                        placeholder="Вес, кг"
                        defaultValue={cp.weight_kg ?? ""}
                        onBlur={(e) => {
                          const v = parseFloat(e.target.value);
                          if (!Number.isFinite(v) || v === cp.weight_kg) return;
                          void updateCargoPlace(
                            (cp as unknown as { id: string }).id,
                            { weight_kg: v }
                          )
                            .then(() =>
                              fetchCargoPlaces(invoice.id).then(setCargoPlaces)
                            )
                            .catch((err) =>
                              toast.error(
                                extractErrorMessage(err) ??
                                  "Не удалось сохранить"
                              )
                            );
                        }}
                        className="h-7 text-xs tabular-nums w-20"
                      />
                      <Input
                        type="number"
                        step="1"
                        min="0"
                        placeholder="Длина"
                        defaultValue={cp.length_mm ?? ""}
                        onBlur={(e) => {
                          const v = parseInt(e.target.value, 10);
                          if (!Number.isFinite(v) || v === cp.length_mm) return;
                          void updateCargoPlace(
                            (cp as unknown as { id: string }).id,
                            { length_mm: v }
                          )
                            .then(() =>
                              fetchCargoPlaces(invoice.id).then(setCargoPlaces)
                            )
                            .catch((err) =>
                              toast.error(
                                extractErrorMessage(err) ??
                                  "Не удалось сохранить"
                              )
                            );
                        }}
                        className="h-7 text-xs tabular-nums w-20"
                      />
                      <Input
                        type="number"
                        step="1"
                        min="0"
                        placeholder="Ширина"
                        defaultValue={cp.width_mm ?? ""}
                        onBlur={(e) => {
                          const v = parseInt(e.target.value, 10);
                          if (!Number.isFinite(v) || v === cp.width_mm) return;
                          void updateCargoPlace(
                            (cp as unknown as { id: string }).id,
                            { width_mm: v }
                          )
                            .then(() =>
                              fetchCargoPlaces(invoice.id).then(setCargoPlaces)
                            )
                            .catch((err) =>
                              toast.error(
                                extractErrorMessage(err) ??
                                  "Не удалось сохранить"
                              )
                            );
                        }}
                        className="h-7 text-xs tabular-nums w-20"
                      />
                      <Input
                        type="number"
                        step="1"
                        min="0"
                        placeholder="Высота"
                        defaultValue={cp.height_mm ?? ""}
                        onBlur={(e) => {
                          const v = parseInt(e.target.value, 10);
                          if (!Number.isFinite(v) || v === cp.height_mm) return;
                          void updateCargoPlace(
                            (cp as unknown as { id: string }).id,
                            { height_mm: v }
                          )
                            .then(() =>
                              fetchCargoPlaces(invoice.id).then(setCargoPlaces)
                            )
                            .catch((err) =>
                              toast.error(
                                extractErrorMessage(err) ??
                                  "Не удалось сохранить"
                              )
                            );
                        }}
                        className="h-7 text-xs tabular-nums w-20"
                      />
                      <span className="text-xs text-muted-foreground">мм</span>
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            await deleteCargoPlace(
                              (cp as unknown as { id: string }).id
                            );
                            const fresh = await fetchCargoPlaces(invoice.id);
                            setCargoPlaces(fresh);
                            toast.success("Место удалено");
                          } catch (err) {
                            console.error(
                              "[invoice-card] deleteCargoPlace failed:",
                              err
                            );
                            toast.error(
                              extractErrorMessage(err) ??
                                "Не удалось удалить место"
                            );
                          }
                        }}
                        className="text-muted-foreground hover:text-destructive ml-auto"
                        title="Удалить место"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : hasCargoPlaces ? (
            <div className="px-4 py-2 bg-muted/30 border-b border-border">
              <div className="flex items-center gap-2 mb-1">
                <Package size={14} className="text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">
                  Грузовые места ({cargoPlaces.length})
                </span>
              </div>
              <div className="space-y-0.5">
                {cargoPlaces.map((cp) => (
                  <div key={cp.position} className="text-xs text-muted-foreground tabular-nums">
                    Место {cp.position}: {cp.weight_kg !== null ? numberFmt.format(cp.weight_kg) : "—"} кг, {cp.length_mm ?? "—"}&times;{cp.width_mm ?? "—"}&times;{cp.height_mm ?? "—"} мм
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          {canSend && (
            <div className="px-4 py-2 bg-muted/30 border-b border-border">
              <div className="flex items-center gap-2 flex-wrap">
                <div
                  role="radiogroup"
                  aria-label="Язык документов"
                  className="inline-flex rounded-md border border-border overflow-hidden"
                >
                  <button
                    type="button"
                    role="radio"
                    aria-checked={language === "ru"}
                    onClick={() => setLanguage("ru")}
                    className={`px-2 py-1 text-xs font-medium transition-colors ${
                      language === "ru"
                        ? "bg-accent text-white"
                        : "bg-background text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    RU
                  </button>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={language === "en"}
                    onClick={() => setLanguage("en")}
                    className={`px-2 py-1 text-xs font-medium transition-colors border-l border-border ${
                      language === "en"
                        ? "bg-accent text-white"
                        : "bg-background text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    EN
                  </button>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={handleDownloadXls}
                  disabled={downloadingXls}
                >
                  {downloadingXls ? (
                    <Loader2 size={14} className="animate-spin mr-1" />
                  ) : (
                    <Download size={14} className="mr-1" />
                  )}
                  Скачать XLS
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs"
                  onClick={() => setComposerOpen(true)}
                >
                  <Mail size={14} className="mr-1" />
                  Подготовить письмо
                </Button>
              </div>
            </div>
          )}

          <SendHistoryPanel invoiceId={invoice.id} />

          {/* Phase 5c: invoice_items list — supplier-side positions with
              coverage summary per row (split/merge indicators). */}
          <div className="overflow-x-auto">
            {invoiceItemsLoading ? (
              <div className="py-6 text-center text-sm text-muted-foreground">
                Загрузка...
              </div>
            ) : !invoiceItems.some(
                (ii) =>
                  coverageSummaryByItem[ii.id] &&
                  // Show only MERGE labels («← X, Y объединены»). Split labels
                  // («→ A ×1 + B ×2») would otherwise repeat for every child
                  // — pure duplication of the handsontable below, since the
                  // split children share their sales-side columns visually.
                  coverageSummaryByItem[ii.id].startsWith("←")
              ) ? null : (
              <div className="border-b border-border bg-muted/20">
                <ul className="divide-y divide-border">
                  {invoiceItems.map((ii) => {
                    const coverage = coverageSummaryByItem[ii.id];
                    // Same gate as the outer null-return: only merge labels.
                    if (!coverage || !coverage.startsWith("←")) return null;
                    return (
                      <li key={ii.id} className="px-4 py-2">
                        <div className="flex items-center gap-2 text-sm">
                          <span className="font-medium truncate">
                            {ii.product_name}
                          </span>
                          {ii.supplier_sku && (
                            <span className="font-mono text-xs text-muted-foreground">
                              {ii.supplier_sku}
                            </span>
                          )}
                          <span className="ml-auto tabular-nums text-muted-foreground">
                            {ii.quantity} ×{" "}
                            {ii.purchase_price_original != null
                              ? `${numberFmtInline.format(ii.purchase_price_original)} ${ii.purchase_currency}`
                              : "\u2014"}
                          </span>
                        </div>
                        {coverage && (
                          <div className="text-xs text-muted-foreground mt-0.5">
                            {coverage}
                          </div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
            <ProcurementItemsEditor
              items={invoiceItems}
              invoiceId={invoice.id}
              procurementCompleted={procurementCompleted}
              salesByItemId={salesByItemId}
              splitableByItemId={splitableByItemId}
              splitChildByItemId={splitChildByItemId}
              mergeableByItemId={mergeableByItemId}
              mergeResultByItemId={mergeResultByItemId}
              onMutated={() => setRefreshKey((k) => k + 1)}
              onUndoMergeRow={async (invoiceItemId) => {
                if (
                  !window.confirm(
                    "Отменить объединение? Объединённая позиция будет удалена и заменена N исходными 1:1 позициями."
                  )
                ) {
                  return;
                }
                try {
                  await undoMerge(invoice.id, invoiceItemId);
                  toast.success("Объединение отменено");
                  setRefreshKey((k) => k + 1);
                } catch (err) {
                  console.error("[invoice-card] undoMerge failed:", err);
                  toast.error(
                    extractErrorMessage(err) ?? "Не удалось отменить объединение"
                  );
                }
              }}
              onMergeRow={(invoiceItemId) => {
                const meta = mergeableByItemId[invoiceItemId];
                if (!meta) return;
                const item = invoiceItems.find((i) => i.id === invoiceItemId);
                setMergeInlineState({
                  initiatorInvoiceItemId: invoiceItemId,
                  initiatorSourceQuoteItemId: meta.sourceQuoteItemId,
                  defaults: {
                    product_name: item?.product_name ?? "",
                    brand: item?.brand ?? "",
                    supplier_sku: item?.supplier_sku ?? "",
                    purchase_price_original:
                      item?.purchase_price_original ?? null,
                  },
                });
              }}
              onSplitRow={(invoiceItemId) => {
                const meta = splitableByItemId[invoiceItemId];
                if (!meta) return;
                const item = invoiceItems.find((i) => i.id === invoiceItemId);
                setSplitInlineState({
                  invoiceItemId,
                  ...meta,
                  defaults: {
                    product_name: item?.product_name ?? "",
                    brand: item?.brand ?? "",
                    supplier_sku: item?.supplier_sku ?? "",
                    purchase_price_original:
                      item?.purchase_price_original ?? null,
                  },
                });
              }}
              onUndoSplitRow={async (invoiceItemId) => {
                const meta = splitChildByItemId[invoiceItemId];
                if (!meta) return;
                if (
                  !window.confirm(
                    `Отменить разделение позиции «${meta.sourceProductName}»? Все дочерние строки будут удалены и заменены одной 1:1.`
                  )
                ) {
                  return;
                }
                try {
                  await undoSplit(invoice.id, meta.sourceQuoteItemId);
                  toast.success("Разделение отменено");
                  setRefreshKey((k) => k + 1);
                } catch (err) {
                  console.error("[invoice-card] undoSplit failed:", err);
                  toast.error(
                    extractErrorMessage(err) ?? "Не удалось отменить разделение"
                  );
                }
              }}
            />
          </div>
        </div>
      )}

      {/* Letter composer items are scoped to THIS invoice — not the whole
          quote — so the «Запрос коммерческого предложения» template lists
          only what this КП covers. The supplier-side row carries
          product_name + quantity + brand directly; product_code (Артикул
          запрошенный) is joined from quote_items via salesByItemId.
          МОЗ Тест 2026-05-01 fail #104 was that the list rendered the
          full quote, not the КП subset. */}
      <LetterDraftComposer
        open={composerOpen}
        onClose={() => {
          setComposerOpen(false);
          router.refresh();
        }}
        invoiceId={invoice.id}
        supplierName={supplierName}
        supplierEmail={(invoice.supplier as { email?: string } | null)?.email ?? null}
        items={invoiceItems.map((ii) => {
          const sales = salesByItemId[ii.id];
          return {
            // The composer reads `product_code`, `product_name`, `quantity`,
            // `brand`, and optional `name_en` from each row. Other QuoteItemRow
            // fields are unused by the template; cast keeps the shape happy.
            // `name_en` originates on quote_items (filled by sales) and is
            // joined via invoice_item_coverage in salesByItemId. When sales
            // hasn't filled it the composer falls back to product_name —
            // mirrors the XLS export's `_get_item_name` behavior.
            id: ii.id,
            quote_id: invoice.quote_id,
            product_code: sales?.product_code ?? ii.supplier_sku ?? "",
            product_name:
              ii.product_name ||
              sales?.product_name ||
              "",
            name_en: sales?.name_en ?? null,
            quantity: ii.quantity,
            brand: ii.brand ?? "",
          } as unknown as QuoteItemRow;
        })}
        currency={currency}
        incoterms={supplierIncoterms}
        pickupCountry={pickupCountryRu}
        initialLanguage={language}
      />

      {/* Inline split: triggered per-row from the procurement handsontable.
          The source quote_item is pre-resolved (see splitableByItemId), so
          this dialog only collects the per-child fields. Replaces the
          top-level SplitModal flow for 1:1 candidates. */}
      <SplitInlineDialog
        open={splitInlineState !== null}
        onClose={() => {
          setSplitInlineState(null);
          // Force re-fetch — invoice.id alone won't trigger the load()
          // effect, so the splitable map (and coverage labels) need an
          // explicit nudge after a successful split.
          setRefreshKey((k) => k + 1);
        }}
        invoiceId={invoice.id}
        sourceQuoteItemId={splitInlineState?.sourceQuoteItemId ?? ""}
        sourceQuantity={splitInlineState?.sourceQuantity ?? 0}
        sourceProductName={splitInlineState?.sourceProductName ?? ""}
        currency={currency}
        defaults={splitInlineState?.defaults}
      />

      {/* Inline merge: per-row trigger from the procurement handsontable.
          Replaces the legacy MergeModal flow. Initiator is the row clicked;
          partner candidates come from the same 1:1-eligibility map split
          uses, minus the initiator. */}
      <MergeInlineDialog
        open={mergeInlineState !== null}
        onClose={() => {
          setMergeInlineState(null);
          // Same refresh trick as split: invoice.id stable → load() won't
          // re-fire on its own → eligibility maps would stay stale.
          setRefreshKey((k) => k + 1);
        }}
        invoiceId={invoice.id}
        initiatorInvoiceItemId={
          mergeInlineState?.initiatorInvoiceItemId ?? ""
        }
        initiatorSourceQuoteItemId={
          mergeInlineState?.initiatorSourceQuoteItemId ?? ""
        }
        initiatorQuantity={(() => {
          const id = mergeInlineState?.initiatorSourceQuoteItemId;
          if (!id) return 0;
          // Look up via the mergeable map (carries source-qi quantity).
          const meta = Object.values(mergeableByItemId).find(
            (m) => m.sourceQuoteItemId === id
          );
          return meta?.sourceQuantity ?? 0;
        })()}
        candidates={Object.entries(mergeableByItemId)
          .filter(
            ([id]) => id !== mergeInlineState?.initiatorInvoiceItemId
          )
          .map(([id, meta]) => {
            const ii = invoiceItems.find((r) => r.id === id);
            return {
              invoice_item_id: id,
              source_quote_item_id: meta.sourceQuoteItemId,
              brand: ii?.brand ?? "",
              supplier_sku: ii?.supplier_sku ?? "",
              product_name: meta.sourceProductName,
              quantity: meta.sourceQuantity,
            };
          })}
        currency={currency}
        defaults={
          mergeInlineState?.defaults ?? {
            product_name: "",
            brand: "",
            supplier_sku: "",
            purchase_price_original: null,
          }
        }
      />

      {/* Task 73 — AddPositionsModal for empty КП (Requirement 7).
          Opened from the isEmpty branch "+ Добавить позиции" button.
          Lets the user pick quote_items to assign into this empty invoice,
          including items already covered by another КП (multi-KP coverage
          is allowed per Phase 5b REQ-1 AC#1). */}
      <AddPositionsModal
        open={addPositionsOpen}
        onClose={() => setAddPositionsOpen(false)}
        invoiceId={invoice.id}
        quoteId={invoice.quote_id}
        onAdded={() => setRefreshKey((k) => k + 1)}
      />

      {/* Add a single cargo place via small dialog. Replaces the older
          placeholder-default insert pattern — user enters real values
          (weight + 3 dims, all > 0) before persistence. */}
      <AddCargoPlaceDialog
        open={addCargoOpen}
        onClose={() => setAddCargoOpen(false)}
        invoiceId={invoice.id}
        onAdded={() => {
          setAddCargoOpen(false);
          void fetchCargoPlaces(invoice.id).then(setCargoPlaces);
        }}
      />

      {/* Confirmation dialog for «Завершить закупку». Stage transition is
          hard to undo (KP locks for editing, kanban advances, downstream
          stages start) — explicit confirmation prevents accidental clicks
          (РОЗ-159 / МОЗ-146). The dialog also blocks completion when the
          КП has no positions or no priced positions: there's nothing to
          send to logistics, so the action would only advance an empty
          record. */}
      <Dialog
        open={completeConfirmOpen}
        onOpenChange={(next) => {
          if (completing) return;
          setCompleteConfirmOpen(next);
        }}
      >
        <DialogContent className="sm:max-w-md z-[200]" showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Завершить закупку?</DialogTitle>
            <DialogDescription>
              {cannotComplete
                ? hasNoPositions
                  ? `КПП ${invoice.invoice_number} не содержит позиций. Добавьте позиции, прежде чем завершать закупку.`
                  : `В КПП ${invoice.invoice_number} ни у одной позиции не указана цена закупки. Заполните цены, прежде чем завершать закупку.`
                : `Закупка по КПП ${invoice.invoice_number} будет завершена. КП перейдёт на этап логистики. Изменения после этого требуют отдельного одобрения. Продолжить?`}
            </DialogDescription>
          </DialogHeader>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCompleteConfirmOpen(false)}
              disabled={completing}
            >
              Отмена
            </Button>
            <Button
              variant="destructive"
              onClick={handleCompleteProcurement}
              disabled={completing || cannotComplete}
            >
              {completing ? (
                <>
                  <Loader2 size={14} className="mr-1 animate-spin" />
                  Завершение…
                </>
              ) : (
                <>
                  <CheckCircle2 size={14} className="mr-1" />
                  Завершить закупку
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
