"use client";

/**
 * Phase 5b CompositionPicker — per-item supplier selection for multi-supplier
 * quotes. Renders inside the CalculationStep as a new card between
 * CalculationForm and CalculationResults.
 *
 * Data flow:
 *   mount  → GET  /api/quotes/{id}/composition
 *   radio  → POST /api/quotes/{id}/composition with { selection: { item_id: invoice_id } }
 *
 * Silent when there is nothing to compose (zero items OR every item has at
 * most one alternative). Shows a warning banner when the composition is
 * incomplete (at least one item has no selected supplier).
 */

import { useCallback, useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type {
  CompositionAlternative,
  CompositionItem,
  CompositionView,
} from "@/entities/quote/types";

interface CompositionPickerProps {
  quoteId: string;
}

async function _getAuthHeader(): Promise<Record<string, string>> {
  const { createClient } = await import("@/shared/lib/supabase/client");
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token
    ? { Authorization: `Bearer ${session.access_token}` }
    : {};
}

async function _fetchComposition(quoteId: string): Promise<CompositionView> {
  const authHeader = await _getAuthHeader();
  const res = await fetch(`/api/quotes/${quoteId}/composition`, {
    headers: authHeader,
  });
  const payload = await res.json();
  if (!res.ok || !payload.success) {
    throw new Error(payload.error?.message || "Failed to load composition");
  }
  return payload.data as CompositionView;
}

async function _postSelection(
  quoteId: string,
  selection: Record<string, string>
): Promise<{ composition_complete: boolean }> {
  const authHeader = await _getAuthHeader();
  const res = await fetch(`/api/quotes/${quoteId}/composition`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader },
    body: JSON.stringify({ selection }),
  });
  const payload = await res.json();
  if (!res.ok || !payload.success) {
    const err = new Error(
      payload.error?.message || "Failed to apply composition"
    );
    (err as Error & { code?: string }).code = payload.error?.code;
    throw err;
  }
  return payload.data ?? { composition_complete: false };
}

export function CompositionPicker({ quoteId }: CompositionPickerProps) {
  const [view, setView] = useState<CompositionView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    _fetchComposition(quoteId)
      .then((data) => {
        if (!cancelled) setView(data);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Network error");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [quoteId]);

  const handleSelect = useCallback(
    async (quoteItemId: string, invoiceId: string) => {
      if (!view) return;

      // Optimistic update
      const optimisticView: CompositionView = {
        ...view,
        items: view.items.map((item) =>
          item.quote_item_id === quoteItemId
            ? { ...item, selected_invoice_id: invoiceId }
            : item
        ),
      };
      const previousView = view;
      setView(optimisticView);
      setSaving(true);

      // Build full selection map from the optimistic state
      const selection: Record<string, string> = {};
      for (const item of optimisticView.items) {
        if (item.selected_invoice_id) {
          selection[item.quote_item_id] = item.selected_invoice_id;
        }
      }

      try {
        const result = await _postSelection(quoteId, selection);
        setView({
          ...optimisticView,
          composition_complete: result.composition_complete,
        });
        toast.success("Поставщик выбран");
      } catch (e: unknown) {
        // Revert optimistic update
        setView(previousView);
        const code =
          e instanceof Error
            ? ((e as Error & { code?: string }).code ?? "")
            : "";
        if (code === "STALE_QUOTE") {
          toast.error("Квота была изменена другим пользователем. Обновите страницу.");
        } else {
          toast.error(
            e instanceof Error ? e.message : "Не удалось сохранить выбор"
          );
        }
      } finally {
        setSaving(false);
      }
    },
    [view, quoteId]
  );

  if (loading) {
    return (
      <Card className="p-6 flex items-center justify-center">
        <Loader2 size={16} className="animate-spin mr-2 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">
          Загружаю композицию...
        </span>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 border-destructive/40">
        <p className="text-sm text-destructive">Ошибка загрузки композиции: {error}</p>
      </Card>
    );
  }

  if (!view || view.items.length === 0) {
    return null;
  }

  // If no item has more than one alternative, there is nothing to compose.
  // Hide the picker — the legacy single-supplier path handles display.
  const hasMultiSupplierChoice = view.items.some(
    (item) => item.alternatives.length > 1
  );
  if (!hasMultiSupplierChoice) {
    return null;
  }

  return (
    <Card className="p-4 md:p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold">Выбор поставщиков</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Выберите поставщика для каждой позиции — на основе этого будет
            посчитан итоговый расчёт.
          </p>
        </div>
        {saving && (
          <Loader2
            size={14}
            className="animate-spin text-muted-foreground shrink-0"
          />
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-4 font-medium">Позиция</th>
              <th className="py-2 px-2 font-medium w-20">Кол-во</th>
              <th className="py-2 px-2 font-medium">Поставщики</th>
            </tr>
          </thead>
          <tbody>
            {view.items.map((item) => (
              <CompositionItemRow
                key={item.quote_item_id}
                item={item}
                disabled={saving || !view.can_edit}
                onSelect={handleSelect}
              />
            ))}
          </tbody>
        </table>
      </div>

      {!view.composition_complete && (
        <p className="mt-3 text-xs text-amber-600 dark:text-amber-400">
          ⚠ Не у всех позиций выбран поставщик — расчёт будет неполным.
        </p>
      )}
    </Card>
  );
}

function CompositionItemRow({
  item,
  disabled,
  onSelect,
}: {
  item: CompositionItem;
  disabled: boolean;
  onSelect: (quoteItemId: string, invoiceId: string) => void;
}) {
  const alternatives = item.alternatives;
  const selected = item.selected_invoice_id;

  return (
    <tr className="border-b border-border/40 last:border-0 align-top">
      <td className="py-3 pr-4">
        <div className="font-medium">{item.name ?? "—"}</div>
        {(item.brand || item.sku) && (
          <div className="text-xs text-muted-foreground">
            {[item.brand, item.sku].filter(Boolean).join(" · ")}
          </div>
        )}
      </td>
      <td className="py-3 px-2 tabular-nums">{item.quantity ?? 1}</td>
      <td className="py-3 px-2">
        {alternatives.length === 0 ? (
          <span className="text-xs text-muted-foreground italic">
            Нет КП поставщиков
          </span>
        ) : alternatives.length === 1 ? (
          <div className="flex items-center gap-2">
            <AlternativeLabel alt={alternatives[0]} />
            <span className="text-[10px] text-muted-foreground">
              (единственное КП)
            </span>
          </div>
        ) : (
          <div className="space-y-1.5">
            {alternatives.map((alt) => (
              <label
                key={alt.invoice_id}
                className="flex items-center gap-2 cursor-pointer hover:bg-muted/40 rounded px-1 py-0.5 -mx-1"
              >
                <input
                  type="radio"
                  name={`composition-${item.quote_item_id}`}
                  value={alt.invoice_id}
                  checked={selected === alt.invoice_id}
                  disabled={disabled}
                  onChange={() => onSelect(item.quote_item_id, alt.invoice_id)}
                  className="h-3.5 w-3.5 cursor-pointer accent-accent disabled:cursor-not-allowed"
                />
                <AlternativeLabel alt={alt} />
              </label>
            ))}
          </div>
        )}
      </td>
    </tr>
  );
}

function AlternativeLabel({ alt }: { alt: CompositionAlternative }) {
  const price =
    alt.purchase_price_original != null
      ? formatPrice(alt.purchase_price_original, alt.purchase_currency)
      : "—";

  return (
    <span className="inline-flex items-center gap-2 flex-wrap">
      <span>{alt.supplier_name ?? "Без поставщика"}</span>
      <span className="tabular-nums text-xs font-medium">{price}</span>
      {alt.supplier_country && (
        <Badge
          variant="outline"
          className="text-[10px] font-normal h-4 px-1.5"
        >
          {alt.supplier_country}
        </Badge>
      )}
    </span>
  );
}

function formatPrice(value: number, currency: string | null): string {
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  return `${formatted} ${currency ?? ""}`.trim();
}
