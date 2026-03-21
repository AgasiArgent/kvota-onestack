"use client";

import { useState, useEffect, useCallback } from "react";
import { Receipt } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { createClient } from "@/shared/lib/supabase/client";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";
import type { DocumentRow } from "./use-control-data";

interface InvoiceComparisonPanelProps {
  quoteId: string;
  invoices: QuoteInvoiceRow[];
  items: QuoteItemRow[];
  invoiceDocuments: Map<string, DocumentRow>;
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

function getInvoiceItems(
  items: QuoteItemRow[],
  invoiceId: string
): QuoteItemRow[] {
  return items.filter((item) => item.invoice_id === invoiceId);
}

function getInvoiceTotal(matchingItems: QuoteItemRow[]): number {
  return matchingItems.reduce((sum, item) => {
    const price = item.purchase_price_original ?? 0;
    const qty = item.quantity ?? 0;
    return sum + price * qty;
  }, 0);
}

export function InvoiceComparisonPanel({
  invoices,
  items,
  invoiceDocuments,
}: InvoiceComparisonPanelProps) {
  const [activeInvoiceId, setActiveInvoiceId] = useState<string | null>(null);
  const [signedUrl, setSignedUrl] = useState<string | null>(null);

  const handleInvoiceClick = useCallback(
    (invoiceId: string) => {
      setActiveInvoiceId((prev) => (prev === invoiceId ? null : invoiceId));
    },
    []
  );

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
        .from("documents")
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

  const activeItems = activeInvoiceId
    ? getInvoiceItems(items, activeInvoiceId)
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
            const matchingItems = getInvoiceItems(items, invoice.id);
            const total = getInvoiceTotal(matchingItems);
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
                            {item.product_name ?? item.product_code ?? "\u2014"}
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
                    src={signedUrl}
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
