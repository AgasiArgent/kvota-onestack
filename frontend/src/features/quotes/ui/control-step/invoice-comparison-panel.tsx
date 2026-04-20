"use client";

import { useState, useEffect, useCallback } from "react";
import { Receipt } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { createClient } from "@/shared/lib/supabase/client";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";
import type { DocumentRow } from "./use-control-data";

/**
 * Phase 5d Task 12 (Agent A) — supplier-side position shape for this panel.
 *
 * Migration 284 drops quote_items.{invoice_id, purchase_price_original,
 * purchase_currency}. Per-invoice positions now live in kvota.invoice_items,
 * which is what this component reads.
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

interface InvoiceComparisonPanelProps {
  quoteId: string;
  invoices: QuoteInvoiceRow[];
  /**
   * Legacy prop retained for interface compatibility with ControlStep.
   * Post-Phase-5c this panel sources positions from invoice_items via an
   * internal Supabase call (Pattern B), so quote_items are not consulted
   * here. Deprecated and removed in Task 16 alongside control-step.tsx.
   */
  items?: QuoteItemRow[];
  invoiceDocuments: Map<string, DocumentRow>;
  /**
   * Test-only override. When provided, the internal Supabase fetch is
   * skipped and these invoice_items are used directly. Mirrors the pattern
   * used in procurement-step/invoice-card.tsx.
   */
  invoiceItemsByInvoiceIdOverride?: Map<string, InvoiceItemRow[]>;
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: "\u20AC",
  USD: "$",
  CNY: "\u00A5",
  RUB: "\u20BD",
};

function formatMoney(value: number, currency: string): string {
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  return `${formatted} ${symbol}`;
}

function sumInvoiceTotal(items: InvoiceItemRow[]): number {
  return items.reduce((sum, item) => {
    const price = item.purchase_price_original ?? 0;
    const qty = item.quantity ?? 0;
    return sum + price * qty;
  }, 0);
}

export function InvoiceComparisonPanel({
  invoices,
  invoiceDocuments,
  invoiceItemsByInvoiceIdOverride,
}: InvoiceComparisonPanelProps) {
  const [activeInvoiceId, setActiveInvoiceId] = useState<string | null>(null);
  const [signedUrl, setSignedUrl] = useState<string | null>(null);
  const [fetchedInvoiceItemsByInvoiceId, setFetchedInvoiceItemsByInvoiceId] =
    useState<Map<string, InvoiceItemRow[]>>(new Map());

  const invoiceItemsByInvoiceId =
    invoiceItemsByInvoiceIdOverride ?? fetchedInvoiceItemsByInvoiceId;

  const handleInvoiceClick = useCallback(
    (invoiceId: string) => {
      setActiveInvoiceId((prev) => (prev === invoiceId ? null : invoiceId));
    },
    []
  );

  // Load invoice_items for all invoices on the panel. Source of truth for
  // per-invoice positions post-migration-284 (quote_items.invoice_id dropped).
  useEffect(() => {
    if (invoiceItemsByInvoiceIdOverride !== undefined) return;

    const supabase = createClient();

    let cancelled = false;
    async function load() {
      const invoiceIds = invoices.map((inv) => inv.id);
      if (invoiceIds.length === 0) {
        if (!cancelled) setFetchedInvoiceItemsByInvoiceId(new Map());
        return;
      }

      const { data, error } = await supabase
        .from("invoice_items")
        .select(
          "id, invoice_id, position, product_name, supplier_sku, brand, quantity, purchase_price_original, purchase_currency"
        )
        .in("invoice_id", invoiceIds);

      if (cancelled) return;

      if (error) {
        console.error("Failed to load invoice_items:", error);
        setFetchedInvoiceItemsByInvoiceId(new Map());
        return;
      }

      const byId = new Map<string, InvoiceItemRow[]>();
      for (const row of data ?? []) {
        const list = byId.get(row.invoice_id) ?? [];
        list.push(row);
        byId.set(row.invoice_id, list);
      }
      // Sort each invoice's items by position for stable display order.
      for (const list of byId.values()) {
        list.sort((a, b) => a.position - b.position);
      }
      setFetchedInvoiceItemsByInvoiceId(byId);
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [invoices, invoiceItemsByInvoiceIdOverride]);

  useEffect(() => {
    if (!activeInvoiceId) {
      setSignedUrl(null);
      return;
    }

    const doc = invoiceDocuments.get(activeInvoiceId);
    if (!doc) {
      setSignedUrl(null);
      return;
    }

    let cancelled = false;
    const supabase = createClient();

    async function fetchSignedUrl(storagePath: string) {
      const { data, error } = await supabase.storage
        .from("kvota-documents")
        .createSignedUrl(storagePath, 3600);

      if (cancelled) return;

      if (error) {
        console.error("Failed to create signed URL:", error);
        setSignedUrl(null);
        return;
      }

      setSignedUrl(data.signedUrl);
    }

    fetchSignedUrl(doc.storage_path);

    return () => {
      cancelled = true;
    };
  }, [activeInvoiceId, invoiceDocuments]);

  if (invoices.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Receipt className="size-5 text-muted-foreground" />
            Инвойсы поставщиков
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Нет инвойсов поставщиков
          </p>
        </CardContent>
      </Card>
    );
  }

  const activeItems: InvoiceItemRow[] = activeInvoiceId
    ? invoiceItemsByInvoiceId.get(activeInvoiceId) ?? []
    : [];
  const activeDoc = activeInvoiceId
    ? invoiceDocuments.get(activeInvoiceId) ?? null
    : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Receipt className="size-5 text-muted-foreground" />
          Инвойсы поставщиков
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Invoice list */}
        <div className="space-y-1">
          {invoices.map((invoice) => {
            const matchingItems =
              invoiceItemsByInvoiceId.get(invoice.id) ?? [];
            const total = sumInvoiceTotal(matchingItems);
            const hasDoc = invoiceDocuments.has(invoice.id);
            const isActive = activeInvoiceId === invoice.id;

            return (
              <button
                key={invoice.id}
                type="button"
                onClick={() => handleInvoiceClick(invoice.id)}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-muted/50"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="font-medium text-foreground">
                    {invoice.invoice_number ?? "Без номера"}
                  </span>
                  <span className="text-muted-foreground">
                    {invoice.supplier?.name ?? "\u2014"}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">
                    {matchingItems.length} поз.
                  </span>
                  <span className="font-medium text-foreground">
                    {formatMoney(total, invoice.currency ?? "USD")}
                  </span>
                  {hasDoc ? (
                    <Badge variant="default" className="bg-green-600 text-white">
                      Скан загружен
                    </Badge>
                  ) : (
                    <Badge variant="destructive">Нет скана</Badge>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Split panel for active invoice */}
        {activeInvoiceId && (
          <div className="flex flex-col gap-4 md:flex-row">
            {/* Left: items table */}
            <div className="w-full md:w-2/5">
              <div className="overflow-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                        Товар
                      </th>
                      <th className="px-3 py-2 text-right font-medium text-muted-foreground">
                        Кол-во
                      </th>
                      <th className="px-3 py-2 text-right font-medium text-muted-foreground">
                        Цена
                      </th>
                      <th className="px-3 py-2 text-left font-medium text-muted-foreground">
                        Валюта
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {activeItems.length === 0 ? (
                      <tr>
                        <td
                          colSpan={4}
                          className="px-3 py-4 text-center text-muted-foreground"
                        >
                          Нет позиций
                        </td>
                      </tr>
                    ) : (
                      activeItems.map((item) => (
                        <tr
                          key={item.id}
                          className="border-b last:border-b-0"
                        >
                          <td className="px-3 py-2 text-foreground">
                            {item.product_name ?? "\u2014"}
                          </td>
                          <td className="px-3 py-2 text-right text-foreground">
                            {item.quantity ?? 0}
                          </td>
                          <td className="px-3 py-2 text-right text-foreground">
                            {item.purchase_price_original != null
                              ? new Intl.NumberFormat("ru-RU", {
                                  minimumFractionDigits: 2,
                                  maximumFractionDigits: 2,
                                }).format(item.purchase_price_original)
                              : "\u2014"}
                          </td>
                          <td className="px-3 py-2 text-muted-foreground">
                            {item.purchase_currency ?? "\u2014"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Right: PDF viewer */}
            <div className="w-full md:w-3/5">
              {activeDoc ? (
                signedUrl ? (
                  <iframe
                    src={`${signedUrl}#toolbar=0&navpanes=0`}
                    title={activeDoc.original_filename}
                    className="h-[500px] w-full rounded-lg border"
                  />
                ) : (
                  <div className="flex h-[500px] items-center justify-center rounded-lg border">
                    <span className="text-sm text-muted-foreground">
                      Загрузка документа...
                    </span>
                  </div>
                )
              ) : (
                <div className="flex h-[500px] items-center justify-center rounded-lg border border-dashed">
                  <span className="text-sm text-muted-foreground">
                    Скан не загружен
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
