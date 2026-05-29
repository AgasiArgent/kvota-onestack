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
import { AlertTriangle, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type {
  CompositionAlternative,
  CompositionItem,
  CompositionView,
} from "@/entities/quote/types";
// historical-fx is a pure, client-safe module. We import it directly rather
// than via the supplier barrel because that barrel also re-exports server-only
// `queries.ts` (createClient from supabase/server), which must not be pulled
// into this client component's bundle.
import {
  buildHistoricalRateMap,
  convertOnDate,
  type FxRateRow,
  type HistoricalRateMap,
} from "@/entities/supplier/lib/historical-fx";
import { currencySymbol, fmtRu } from "@/entities/kp-proposal";

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

/**
 * Testing 2 row 36 — fetch the historical FX rate map client-side, reusing
 * the same `* → RUB` shape the /suppliers aggregate consumes
 * (entities/supplier/queries.ts). RUB is the implicit base; convertOnDate
 * derives any cross-rate from the two `→ RUB` legs. Returns an empty map on
 * error so the picker still renders (price shown, tooltip omitted).
 */
async function _fetchRates(): Promise<HistoricalRateMap> {
  try {
    const { createClient } = await import("@/shared/lib/supabase/client");
    const supabase = createClient();
    const { data, error } = await supabase
      .from("exchange_rates")
      .select("from_currency, rate, fetched_at")
      .eq("to_currency", "RUB");
    if (error) throw error;
    return buildHistoricalRateMap((data ?? []) as FxRateRow[]);
  } catch (e) {
    console.error("[composition-picker] failed to load exchange_rates", e);
    return buildHistoricalRateMap([]);
  }
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

/**
 * Testing 2 row 90 — persist МОП's per-item include/exclude decision.
 *
 * Distinct from `_postSelection`: that one picks WHICH supplier per item.
 * This one decides whether the item participates in the calc at all. The
 * backend filter sits in `build_calculation_inputs()` so excluded rows are
 * dropped before reaching the locked calc engine.
 */
async function _postInclusion(
  quoteId: string,
  inclusion: Record<string, boolean>
): Promise<{ updated: number }> {
  const authHeader = await _getAuthHeader();
  const res = await fetch(`/api/quotes/${quoteId}/inclusion`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader },
    body: JSON.stringify({ inclusion }),
  });
  const payload = await res.json();
  if (!res.ok || !payload.success) {
    const err = new Error(
      payload.error?.message || "Failed to apply inclusion"
    );
    (err as Error & { code?: string }).code = payload.error?.code;
    throw err;
  }
  return payload.data ?? { updated: 0 };
}

export function CompositionPicker({ quoteId }: CompositionPickerProps) {
  const [view, setView] = useState<CompositionView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // Testing 2 row 36: historical FX rate map for the Цена tooltip. Loaded
  // once alongside the composition; an empty map (load failure / no rates)
  // just means the tooltip is omitted — the price still renders.
  const [rates, setRates] = useState<HistoricalRateMap>(() =>
    buildHistoricalRateMap([])
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    // Composition and FX rates are independent reads — fetch concurrently.
    Promise.all([_fetchComposition(quoteId), _fetchRates()])
      .then(([data, rateMap]) => {
        if (!cancelled) {
          setView(data);
          setRates(rateMap);
        }
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

  const handleToggleInclusion = useCallback(
    async (quoteItemId: string, included: boolean) => {
      if (!view) return;

      // Optimistic update
      const previousView = view;
      const optimisticView: CompositionView = {
        ...view,
        items: view.items.map((item) =>
          item.quote_item_id === quoteItemId
            ? { ...item, included_in_calc: included }
            : item
        ),
      };
      setView(optimisticView);
      setSaving(true);

      try {
        await _postInclusion(quoteId, { [quoteItemId]: included });
        toast.success(
          included ? "Позиция включена в расчёт" : "Позиция исключена из расчёта"
        );
      } catch (e: unknown) {
        setView(previousView);
        toast.error(
          e instanceof Error ? e.message : "Не удалось сохранить выбор"
        );
      } finally {
        setSaving(false);
      }
    },
    [view, quoteId]
  );

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

  // Testing 2 row 90: the picker now also hosts the МОП "include/exclude"
  // toggle, so show it whenever there is more than one alternative OR more
  // than one item (the latter is the case where МОП wants to drop a line
  // even though there's a single supplier). For single-item single-supplier
  // quotes there is genuinely nothing to compose — keep the legacy hide.
  const hasMultiSupplierChoice = view.items.some(
    (item) => item.alternatives.length > 1
  );
  const hasMultipleItems = view.items.length > 1;
  if (!hasMultiSupplierChoice && !hasMultipleItems) {
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
              <th className="py-2 pr-2 font-medium w-12 text-center">В&nbsp;расчёт</th>
              <th className="py-2 pr-4 font-medium">Позиция</th>
              <th className="py-2 px-2 font-medium w-20">Кол-во</th>
              <th className="py-2 px-2 font-medium w-28">Цена</th>
              <th className="py-2 px-2 font-medium w-28">Сумма</th>
              <th className="py-2 px-2 font-medium">Поставщики</th>
            </tr>
          </thead>
          <tbody>
            {view.items.map((item) => (
              <CompositionItemRow
                key={item.quote_item_id}
                item={item}
                disabled={saving || !view.can_edit}
                rates={rates}
                kpCurrency={view.currency_of_quote ?? null}
                onSelect={handleSelect}
                onToggleInclusion={handleToggleInclusion}
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

export function CompositionItemRow({
  item,
  disabled,
  rates,
  kpCurrency,
  onSelect,
  onToggleInclusion,
}: {
  item: CompositionItem;
  disabled: boolean;
  /**
   * Testing 2 row 36 — historical FX rate map + КП currency for the Цена
   * tooltip. Both optional so the picker-coverage tests (which render the
   * row directly with renderToString) keep their pre-row-36 prop signature;
   * when absent the tooltip is simply omitted and only the price shows.
   */
  rates?: HistoricalRateMap;
  kpCurrency?: string | null;
  onSelect: (quoteItemId: string, invoiceId: string) => void;
  /**
   * Testing 2 row 90 — МОП toggle for including/excluding the row from the
   * calc. Optional so the picker-coverage tests (which exercise the
   * `coverage_summary`/`divergent_markups` rendering only) keep their
   * pre-row-90 prop signature. When omitted the checkbox is a no-op.
   */
  onToggleInclusion?: (quoteItemId: string, included: boolean) => void;
}) {
  const alternatives = item.alternatives;
  const selected = item.selected_invoice_id;
  // Treat undefined as included — coverage-summary tests construct items
  // without the new flag, and pre-migration rows from the API will eventually
  // surface as true once the migration runs.
  const included = item.included_in_calc !== false;

  // Testing 2 row 36: the Цена/Сумма columns reflect the SELECTED КПП — the
  // alternative whose invoice_id matches the item's composition pointer. When
  // nothing is selected (or it has no price) both cells render "—".
  const selectedAlt =
    selected != null
      ? alternatives.find((alt) => alt.invoice_id === selected) ?? null
      : null;

  // Testing 2 row 90: when МОП excludes a row we grey it out and surface the
  // reason label. The toggle stays interactive so МОП can re-include it.
  return (
    <tr
      className={`border-b border-border/40 last:border-0 align-top ${
        included ? "" : "opacity-50"
      }`}
    >
      <td className="py-3 pr-2 text-center">
        <input
          type="checkbox"
          aria-label="Включить позицию в расчёт"
          checked={included}
          disabled={disabled || !onToggleInclusion}
          onChange={(e) =>
            onToggleInclusion?.(item.quote_item_id, e.target.checked)
          }
          className="h-4 w-4 cursor-pointer accent-accent disabled:cursor-not-allowed"
        />
      </td>
      <td className="py-3 pr-4">
        <div className="font-medium">{item.name ?? "—"}</div>
        {(item.brand || item.sku) && (
          <div className="text-xs text-muted-foreground">
            {[item.brand, item.sku].filter(Boolean).join(" · ")}
          </div>
        )}
        {!included && (
          <div className="text-xs italic text-amber-600 dark:text-amber-400 mt-0.5">
            Исключено по решению МОП
          </div>
        )}
      </td>
      <td className="py-3 px-2 tabular-nums">{item.quantity ?? 1}</td>
      <PriceCell alt={selectedAlt} rates={rates} kpCurrency={kpCurrency} />
      <SumCell alt={selectedAlt} quantity={item.quantity} />
      <td className="py-3 px-2">
        {alternatives.length === 0 ? (
          <span className="text-xs text-muted-foreground italic">
            Нет КП поставщиков
          </span>
        ) : alternatives.length === 1 ? (
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2">
              <AlternativeLabel alt={alternatives[0]} />
              <span className="text-[10px] text-muted-foreground">
                (единственное КП)
              </span>
            </div>
            <AlternativeSubtext alt={alternatives[0]} />
          </div>
        ) : (
          <div className="space-y-1.5">
            {alternatives.map((alt) => (
              <label
                key={alt.invoice_id}
                className="flex items-start gap-2 cursor-pointer hover:bg-muted/40 rounded px-1 py-0.5 -mx-1"
              >
                <input
                  type="radio"
                  name={`composition-${item.quote_item_id}`}
                  value={alt.invoice_id}
                  checked={selected === alt.invoice_id}
                  disabled={disabled || !included}
                  onChange={() => onSelect(item.quote_item_id, alt.invoice_id)}
                  className="h-3.5 w-3.5 mt-1 cursor-pointer accent-accent disabled:cursor-not-allowed"
                />
                <div className="flex flex-col gap-0.5 min-w-0">
                  <AlternativeLabel alt={alt} />
                  <AlternativeSubtext alt={alt} />
                </div>
              </label>
            ))}
          </div>
        )}
      </td>
    </tr>
  );
}

function AlternativeLabel({ alt }: { alt: CompositionAlternative }) {
  // Testing 2 row 36: the per-supplier price moved out of this label into the
  // dedicated Цена column — keep only supplier name, country badge, and the
  // divergent-markups warning here to avoid showing the price twice.
  return (
    <span className="inline-flex items-center gap-2 flex-wrap">
      <span>{alt.supplier_name ?? "Без поставщика"}</span>
      {alt.supplier_country && (
        <Badge
          variant="outline"
          className="text-[10px] font-normal h-4 px-1.5"
        >
          {alt.supplier_country}
        </Badge>
      )}
      {alt.divergent_markups && (
        <span
          title="Покрываемые позиции имеют разные наценки — применится первая"
          className="inline-flex items-center text-amber-500"
          aria-label="Покрываемые позиции имеют разные наценки — применится первая"
        >
          <AlertTriangle size={12} />
        </span>
      )}
    </span>
  );
}

function AlternativeSubtext({ alt }: { alt: CompositionAlternative }) {
  if (!alt.coverage_summary) {
    return null;
  }
  return (
    <span className="text-xs text-muted-foreground italic">
      {alt.coverage_summary}
    </span>
  );
}

/**
 * Testing 2 row 36 — unit price of the SELECTED КПП in the supplier's local
 * currency. When the historical FX map, the КП currency, and the КПП date are
 * all available, the cell carries a `title` tooltip showing the КП-currency
 * equivalent at the rate effective on the КПП date. Conversion failures (no
 * rate, missing date) silently drop the tooltip — the original price always
 * renders. Greyed when the row is excluded from the calc, consistent with the
 * surrounding row (the parent <tr> sets opacity-50).
 */
function PriceCell({
  alt,
  rates,
  kpCurrency,
}: {
  alt: CompositionAlternative | null;
  rates?: HistoricalRateMap;
  kpCurrency?: string | null;
}) {
  if (!alt || alt.purchase_price_original == null) {
    return <td className="py-3 px-2 tabular-nums text-muted-foreground">—</td>;
  }

  const price = alt.purchase_price_original;
  const tooltip = buildKpEquivalentTooltip(
    price,
    alt.purchase_currency,
    kpCurrency,
    alt.kpp_date,
    rates
  );

  return (
    <td
      className="py-3 px-2 tabular-nums whitespace-nowrap"
      title={tooltip ?? undefined}
    >
      {formatPrice(price, alt.purchase_currency)}
    </td>
  );
}

/**
 * Testing 2 row 36 — line total for the SELECTED КПП:
 * purchase_price_original × quantity, in the supplier's local currency.
 * Uses item.quantity (the only quantity exposed to the picker — the
 * per-invoice_item quantity the calc engine uses is not surfaced on the
 * alternative payload). "—" when no priced КПП is selected.
 */
function SumCell({
  alt,
  quantity,
}: {
  alt: CompositionAlternative | null;
  quantity: number | null;
}) {
  if (!alt || alt.purchase_price_original == null) {
    return <td className="py-3 px-2 tabular-nums text-muted-foreground">—</td>;
  }
  const qty = quantity ?? 1;
  return (
    <td className="py-3 px-2 tabular-nums whitespace-nowrap">
      {formatPrice(alt.purchase_price_original * qty, alt.purchase_currency)}
    </td>
  );
}

/**
 * Build the КП-currency-equivalent tooltip string for a supplier-local price.
 * Returns null when any required input is missing or the historical
 * conversion is unavailable — callers then render no tooltip rather than a
 * broken "0" or partial value.
 */
function buildKpEquivalentTooltip(
  price: number,
  fromCurrency: string | null,
  kpCurrency: string | null | undefined,
  kppDate: string | null | undefined,
  rates: HistoricalRateMap | undefined
): string | null {
  if (!rates || !kpCurrency || !fromCurrency || !kppDate) return null;
  const equivalent = convertOnDate(price, fromCurrency, kpCurrency, kppDate, rates);
  if (equivalent == null) return null;
  return `≈ ${fmtRu(equivalent)} ${currencySymbol(kpCurrency)} (по курсу на ${formatKppDate(kppDate)})`;
}

/** Format an ISO КПП timestamp as a DD.MM.YYYY date for the tooltip. */
function formatKppDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(d);
}

function formatPrice(value: number, currency: string | null): string {
  const formatted = new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
  return `${formatted} ${currency ?? ""}`.trim();
}
