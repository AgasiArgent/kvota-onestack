"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, ChevronRight, Download, Loader2, Mail, Package, Paperclip, Trash2, Undo2, Weight } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ProcurementItemsEditor } from "./procurement-items-editor";
import { SendHistoryPanel } from "./send-history-panel";
import { ProcurementUnlockButton } from "./procurement-unlock-button";
import { LetterDraftComposer } from "./letter-draft-composer";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";
import { deleteInvoice, fetchCargoPlaces } from "@/entities/quote/mutations";
import { downloadInvoiceXls } from "@/entities/invoice/mutations";
import { createClient } from "@/shared/lib/supabase/client";
import { findCountryByCode } from "@/shared/ui/geo";

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
 */
export interface InvoiceItemRow {
  id: string;
  invoice_id: string;
  position: number;
  product_name: string;
  supplier_sku: string | null;
  brand: string | null;
  quantity: number;
  purchase_price_original: number | null;
  purchase_currency: string;
}

/**
 * Minimal quote stub used for edit-gate computation. Parent may pass a full
 * QuoteDetailRow — any superset with these fields works. `items` stays as
 * QuoteItemRow[] because several sibling editors (ProcurementItemsEditor,
 * LetterDraftComposer, XLS export) still read customer-side fields from it.
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
}

const numberFmtInline = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function InvoiceCard({
  invoice,
  items,
  quote,
  invoiceItems: invoiceItemsOverride,
  coverageSummaryByItem: coverageOverride,
  defaultExpanded = false,
  userRoles = [],
}: InvoiceCardProps) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [unassigning, setUnassigning] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [downloadingXls, setDownloadingXls] = useState(false);
  const [composerOpen, setComposerOpen] = useState(false);
  const [language, setLanguage] = useState<"ru" | "en">("ru");
  const [cargoPlaces, setCargoPlaces] = useState<
    Array<{ position: number; weight_kg: number; length_mm: number; width_mm: number; height_mm: number }>
  >([]);
  const [weightKg, setWeightKg] = useState(invoice.total_weight_kg?.toString() ?? "");
  const [volumeM3, setVolumeM3] = useState(invoice.total_volume_m3?.toString() ?? "");
  const [fetchedInvoiceItems, setFetchedInvoiceItems] = useState<
    InvoiceItemRow[]
  >([]);
  const [fetchedCoverage, setFetchedCoverage] = useState<Record<string, string>>({});
  const [invoiceItemsLoading, setInvoiceItemsLoading] = useState(
    invoiceItemsOverride === undefined
  );

  const procurementCompleted = quote.procurement_completed_at != null;
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
    // database.types.ts does not include invoice_items / invoice_item_coverage
    // yet (migrations 281-282 add them). Cast through `from` to bypass the
    // missing types.
    const supabase = createClient();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const untyped = supabase as unknown as { from: (t: string) => any };

    let cancelled = false;
    async function load() {
      setInvoiceItemsLoading(true);
      try {
        const { data: ii } = await untyped
          .from("invoice_items")
          .select(
            "id, invoice_id, position, product_name, supplier_sku, brand, quantity, purchase_price_original, purchase_currency"
          )
          .eq("invoice_id", invoice.id)
          .order("position", { ascending: true });
        if (cancelled) return;
        const rows = (ii ?? []) as InvoiceItemRow[];
        setFetchedInvoiceItems(rows);

        if (rows.length === 0) {
          setFetchedCoverage({});
          return;
        }

        // Coverage summary: for each invoice_item, fetch its coverage rows
        // (and sibling coverage for merge detection). Labels:
        //   split  = 1 quote_item → N invoice_items → "→ A ×1 + B ×2"
        //   merge  = N quote_items → 1 invoice_item → "← A, B, C объединены"
        //   1:1    = no entry in map
        const { data: cov } = await untyped
          .from("invoice_item_coverage")
          .select(
            "invoice_item_id, quote_item_id, ratio, quote_items!inner(product_name)"
          )
          .in(
            "invoice_item_id",
            rows.map((r) => r.id)
          );

        const coverageByIi = new Map<
          string,
          Array<{ quote_item_id: string; ratio: number; product_name: string }>
        >();
        const iiByQi = new Map<string, string[]>();
        for (const row of (cov ?? []) as Array<{
          invoice_item_id: string;
          quote_item_id: string;
          ratio: number;
          quote_items: { product_name: string };
        }>) {
          const list = coverageByIi.get(row.invoice_item_id) ?? [];
          list.push({
            quote_item_id: row.quote_item_id,
            ratio: row.ratio,
            product_name: row.quote_items?.product_name ?? "",
          });
          coverageByIi.set(row.invoice_item_id, list);

          const iis = iiByQi.get(row.quote_item_id) ?? [];
          iis.push(row.invoice_item_id);
          iiByQi.set(row.quote_item_id, iis);
        }

        const summary: Record<string, string> = {};
        for (const ii of rows) {
          const covers = coverageByIi.get(ii.id) ?? [];
          if (covers.length > 1) {
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
            }
            // else 1:1 — no label
          }
        }
        if (!cancelled) setFetchedCoverage(summary);
      } finally {
        if (!cancelled) setInvoiceItemsLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [invoice.id, invoiceItemsOverride]);

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

  const cargoWeight = cargoPlaces.reduce((sum, cp) => sum + cp.weight_kg, 0);
  const cargoVolume = cargoPlaces.reduce(
    (sum, cp) => sum + (cp.length_mm * cp.width_mm * cp.height_mm) / 1e9,
    0
  );
  const hasCargoPlaces = cargoPlaces.length > 0;

  const hasInvoiceWeight = invoice.total_weight_kg != null || invoice.total_volume_m3 != null;

  async function handleSaveField(field: "total_weight_kg" | "total_volume_m3", raw: string) {
    const value = raw.trim() === "" ? null : Number(raw);
    if (value !== null && isNaN(value)) return;
    try {
      const supabase = (await import("@/shared/lib/supabase/client")).createClient();
      const { error } = await supabase
        .from("invoices")
        .update({ [field]: value })
        .eq("id", invoice.id);
      if (error) throw error;
      toast.success("Сохранено");
      router.refresh();
    } catch {
      toast.error("Не удалось сохранить");
    }
  }

  async function handleDownloadXls() {
    setDownloadingXls(true);
    try {
      await downloadInvoiceXls(invoice.id, language);
      toast.success("XLS скачан");
      router.refresh();
    } catch {
      toast.error("Не удалось скачать XLS");
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const untyped = supabase as unknown as { from: (t: string) => any };

      if (invoiceItems.length > 0) {
        const { error: delErr } = await untyped
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
    } catch {
      toast.error("Не удалось убрать позиции из КП");
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
    } catch {
      toast.error("Не удалось удалить КП");
    } finally {
      setDeleting(false);
    }
  }

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

          {pickupLocationLabel && (
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">
              {pickupLocationLabel}
            </span>
          )}

          {supplierIncoterms && (
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">
              Условия: {supplierIncoterms}
            </span>
          )}

          {hasInvoiceWeight && (
            <span className="text-xs text-muted-foreground tabular-nums shrink-0 hidden sm:inline">
              {invoice.total_weight_kg != null && <>{numberFmt.format(invoice.total_weight_kg)}&nbsp;кг</>}
              {invoice.total_weight_kg != null && invoice.total_volume_m3 != null && " · "}
              {invoice.total_volume_m3 != null && <>{numberFmt.format(invoice.total_volume_m3)}&nbsp;м&sup3;</>}
            </span>
          )}

          {hasCargoPlaces && (
            <span className="text-xs text-muted-foreground tabular-nums shrink-0 hidden sm:inline">
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
            // The edit-gate is driven by quote.procurement_completed_at.
            <Badge variant="default" className="shrink-0 text-xs bg-green-600">
              Отправлено {new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit" }).format(new Date(sentAt!))}
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
          <Button
            variant="ghost"
            size="sm"
            className="mr-2 text-muted-foreground hover:text-destructive"
            onClick={handleDelete}
            disabled={deleting}
            title="Удалить пустое КП поставщику"
          >
            {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          </Button>
        ) : (
          <Button
            variant="ghost"
            size="sm"
            className="mr-2 text-muted-foreground hover:text-destructive"
            onClick={handleUnassignAll}
            disabled={unassigning}
            title="Вернуть все позиции в нераспределённые"
          >
            {unassigning ? <Loader2 size={14} className="animate-spin" /> : <Undo2 size={14} />}
          </Button>
        )}
      </div>

      {expanded && (
        <div className="border-t border-border">
          {!procurementCompleted ? (
            <div className="px-4 py-2 bg-muted/30 border-b border-border">
              <div className="flex items-center gap-2 mb-1">
                <Weight size={14} className="text-muted-foreground" />
                <span className="text-xs font-medium text-muted-foreground">
                  Вес и габариты
                </span>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="Вес"
                    value={weightKg}
                    onChange={(e) => setWeightKg(e.target.value)}
                    onBlur={() => handleSaveField("total_weight_kg", weightKg)}
                    className="h-7 w-24 text-xs tabular-nums"
                  />
                  <span className="text-xs text-muted-foreground">кг</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    placeholder="Объём"
                    value={volumeM3}
                    onChange={(e) => setVolumeM3(e.target.value)}
                    onBlur={() => handleSaveField("total_volume_m3", volumeM3)}
                    className="h-7 w-24 text-xs tabular-nums"
                  />
                  <span className="text-xs text-muted-foreground">м³</span>
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
          {hasCargoPlaces && (
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
                    Место {cp.position}: {numberFmt.format(cp.weight_kg)} кг, {cp.length_mm}&times;{cp.width_mm}&times;{cp.height_mm} мм
                  </div>
                ))}
              </div>
            </div>
          )}
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
            ) : invoiceItems.length === 0 ? null : (
              <div className="border-b border-border bg-muted/20">
                <ul className="divide-y divide-border">
                  {invoiceItems.map((ii) => {
                    const coverage = coverageSummaryByItem[ii.id];
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
            <ProcurementItemsEditor items={items} invoiceId={invoice.id} procurementCompleted={procurementCompleted} />
          </div>
        </div>
      )}

      <LetterDraftComposer
        open={composerOpen}
        onClose={() => {
          setComposerOpen(false);
          router.refresh();
        }}
        invoiceId={invoice.id}
        supplierName={supplierName}
        supplierEmail={(invoice.supplier as { email?: string } | null)?.email ?? null}
        items={items}
        currency={currency}
        incoterms={supplierIncoterms}
        pickupCountry={pickupCountryRu}
        initialLanguage={language}
      />
    </Card>
  );
}
