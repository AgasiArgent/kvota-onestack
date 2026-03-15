"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { FileDown, ArrowLeft } from "lucide-react";
import { toast, Toaster } from "sonner";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type {
  PhmbQuoteDetail,
  PhmbQuoteItem,
  PriceListSearchResult,
  CalcResult,
} from "@/entities/phmb-quote/types";
import {
  addItemToQuote,
  updateItemQuantity,
  updateItemPrice,
  deleteItem as deleteItemMutation,
  savePaymentTerms,
  calculateQuote,
  exportPdf,
} from "@/entities/phmb-quote/mutations";
import { ItemSearch } from "./item-search";
import { ItemsTable } from "./items-table";
import { PaymentTermsPanel } from "./payment-terms-panel";
import { VersionPills } from "./version-pills";

interface QuoteWorkspaceProps {
  quote: PhmbQuoteDetail;
  items: PhmbQuoteItem[];
  orgId: string;
}

export function QuoteWorkspace({
  quote,
  items: initialItems,
  orgId,
}: QuoteWorkspaceProps) {
  const [items, setItems] = useState<PhmbQuoteItem[]>(initialItems);
  const [terms, setTerms] = useState({
    phmb_advance_pct: quote.phmb_advance_pct,
    phmb_payment_days: quote.phmb_payment_days,
    phmb_markup_pct: quote.phmb_markup_pct,
  });
  const [isCalculating, setIsCalculating] = useState(false);
  const [isSavingTerms, setIsSavingTerms] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [totals, setTotals] = useState<CalcResult["totals"] | null>(null);

  const calcTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pricedCount = items.filter((i) => i.status === "priced").length;
  const totalCount = items.length;
  const hasWaitingItems = pricedCount < totalCount && totalCount > 0;

  const triggerCalculation = useCallback(async () => {
    if (items.length === 0) return;
    setIsCalculating(true);
    try {
      const result = await calculateQuote(quote.id);
      setTotals(result.totals);

      // Update items with calculated values
      setItems((prev) =>
        prev.map((item) => {
          const calcItem = result.items.find((c) => c.id === item.id);
          if (!calcItem) return item;
          return {
            ...item,
            exw_price_usd: calcItem.exw_price_usd,
            cogs_usd: calcItem.cogs_usd,
            financial_cost_usd: calcItem.financial_cost_usd,
            total_price_usd: calcItem.total_price_usd,
            total_price_with_vat_usd: calcItem.total_price_with_vat_usd,
          };
        })
      );
    } catch {
      toast.error("Ошибка расчёта. Попробуйте ещё раз.");
    } finally {
      setIsCalculating(false);
    }
  }, [items.length, quote.id]);

  const debouncedCalc = useCallback(() => {
    if (calcTimeoutRef.current) clearTimeout(calcTimeoutRef.current);
    calcTimeoutRef.current = setTimeout(triggerCalculation, 500);
  }, [triggerCalculation]);

  useEffect(() => {
    return () => {
      if (calcTimeoutRef.current) clearTimeout(calcTimeoutRef.current);
    };
  }, []);

  const handleAddItem = useCallback(
    async (priceListItem: PriceListSearchResult) => {
      try {
        const newItem = await addItemToQuote(quote.id, orgId, priceListItem);
        setItems((prev) => [...prev, newItem]);
        if (newItem.status === "priced") {
          debouncedCalc();
        }
      } catch {
        toast.error("Не удалось добавить позицию.");
      }
    },
    [quote.id, orgId, debouncedCalc]
  );

  const handleUpdateItem = useCallback(
    async (id: string, field: string, value: number | string) => {
      try {
        if (field === "quantity") {
          const qty = typeof value === "number" ? value : parseInt(String(value), 10);
          if (isNaN(qty) || qty <= 0) return;
          await updateItemQuantity(id, qty);
          setItems((prev) =>
            prev.map((item) =>
              item.id === id ? { ...item, quantity: qty } : item
            )
          );
          debouncedCalc();
        } else if (field === "list_price_rmb") {
          const price = typeof value === "number" ? value : parseFloat(String(value));
          if (isNaN(price) || price < 0) return;
          const item = items.find((i) => i.id === id);
          await updateItemPrice(id, price, item?.discount_pct ?? 0);
          setItems((prev) =>
            prev.map((i) =>
              i.id === id
                ? {
                    ...i,
                    list_price_rmb: price,
                    status: price > 0 ? ("priced" as const) : ("waiting" as const),
                  }
                : i
            )
          );
          debouncedCalc();
        }
      } catch {
        toast.error("Не удалось обновить позицию.");
      }
    },
    [items, debouncedCalc]
  );

  const handleDeleteItem = useCallback(
    async (id: string) => {
      try {
        await deleteItemMutation(id);
        setItems((prev) => prev.filter((item) => item.id !== id));
      } catch {
        toast.error("Не удалось удалить позицию.");
      }
    },
    []
  );

  const handleSaveTerms = useCallback(
    async (newTerms: typeof terms) => {
      setIsSavingTerms(true);
      try {
        await savePaymentTerms(quote.id, newTerms);
        setTerms(newTerms);
        debouncedCalc();
        toast.success("Условия оплаты сохранены.");
      } catch {
        toast.error("Не удалось сохранить условия.");
      } finally {
        setIsSavingTerms(false);
      }
    },
    [quote.id, debouncedCalc]
  );

  const handleExportPdf = useCallback(async () => {
    setIsExporting(true);
    try {
      const blob = await exportPdf(quote.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${quote.idn_quote}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Ошибка экспорта PDF. Попробуйте позже.");
    } finally {
      setIsExporting(false);
    }
  }, [quote.id, quote.idn_quote]);

  const handleExportPartial = useCallback(async () => {
    setIsExporting(true);
    try {
      const blob = await exportPdf(quote.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${quote.idn_quote}-partial.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Ошибка экспорта PDF. Попробуйте позже.");
    } finally {
      setIsExporting(false);
    }
  }, [quote.id, quote.idn_quote]);

  function formatAmount(amount: number | null | undefined) {
    if (amount === null || amount === undefined || amount === 0) return "—";
    return new Intl.NumberFormat("ru-RU", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(amount);
  }

  return (
    <div className="flex flex-col h-full gap-4">
      <Toaster position="top-right" richColors />

      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/phmb"
            className="text-text-muted hover:text-text transition-colors"
          >
            <ArrowLeft size={20} />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold">{quote.idn_quote}</h1>
              <Badge
                variant="outline"
                className="bg-secondary text-secondary-foreground"
              >
                {quote.customer_name}
              </Badge>
              <VersionPills quoteId={quote.id} currentLabel="v1" />
            </div>
            <div className="flex items-center gap-3 mt-1 text-sm text-text-muted">
              <span className="tabular-nums">
                {pricedCount}/{totalCount} позиций с ценой
              </span>
              {totals && (
                <>
                  <span className="text-border">|</span>
                  <span className="tabular-nums">
                    Итого: {formatAmount(totals.total_with_vat_usd)}
                  </span>
                </>
              )}
              {isCalculating && (
                <span className="text-accent text-xs">Расчёт...</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {hasWaitingItems && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportPartial}
              disabled={isExporting || pricedCount === 0}
            >
              <FileDown size={16} />
              <span className="hidden sm:inline">
                КП из {pricedCount} готовых
              </span>
            </Button>
          )}
          <Button
            size="sm"
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleExportPdf}
            disabled={isExporting || totalCount === 0}
          >
            <FileDown size={16} />
            <span className="hidden sm:inline">PDF</span>
          </Button>
        </div>
      </div>

      {/* Search */}
      <ItemSearch onAddItem={handleAddItem} orgId={orgId} />

      {/* Table */}
      <div className="flex-1 min-h-0">
        <ItemsTable
          items={items}
          onUpdateItem={handleUpdateItem}
          onDeleteItem={handleDeleteItem}
          totals={totals}
        />
      </div>

      {/* Payment Terms */}
      <PaymentTermsPanel
        terms={terms}
        onSave={handleSaveTerms}
        isSaving={isSavingTerms}
      />
    </div>
  );
}
