"use client";

import { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Package } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";
import { fetchCargoPlaces } from "@/entities/quote/mutations";
import { ProductsSubtable } from "./products-subtable";
import { RouteSegments } from "./route-segments";
import { AdditionalExpenses } from "./additional-expenses";

const numberFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/**
 * Phase 5d Task 14: per-invoice logistics weight is aggregated from
 * `invoice_items.weight_in_kg` (the supplier-side per-position weight).
 * Legacy `quote_items.weight_in_kg` is dropped in migration 284.
 */
export interface LogisticsWeightItem {
  quantity: number;
  weight_in_kg: number | null;
}

export interface CargoPlace {
  weight_kg: number;
}

export function computeTotalWeight(
  invoiceItems: LogisticsWeightItem[],
  cargoPlaces: CargoPlace[]
): number {
  if (cargoPlaces.length > 0) {
    return cargoPlaces.reduce((sum, cp) => sum + cp.weight_kg, 0);
  }
  return invoiceItems.reduce(
    (sum, item) => sum + (item.weight_in_kg ?? 0) * item.quantity,
    0
  );
}

interface LogisticsInvoiceRowProps {
  invoice: QuoteInvoiceRow;
  items: QuoteItemRow[];
  deliveryCity: string | null;
  defaultExpanded?: boolean;
}

export function LogisticsInvoiceRow({
  invoice,
  items,
  deliveryCity,
  defaultExpanded = false,
}: LogisticsInvoiceRowProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [cargoPlaces, setCargoPlaces] = useState<
    Array<{ position: number; weight_kg: number; length_mm: number; width_mm: number; height_mm: number }>
  >([]);

  useEffect(() => {
    fetchCargoPlaces(invoice.id).then(setCargoPlaces);
  }, [invoice.id]);

  const supplierName =
    (invoice.supplier as { name: string } | null)?.name ?? "\u2014";

  const pickup = [invoice.pickup_city, invoice.pickup_country]
    .filter(Boolean)
    .join(", ");
  const destination = deliveryCity ?? "\u2014";

  const hasCargoPlaces = cargoPlaces.length > 0;
  const cargoWeight = cargoPlaces.reduce((sum, cp) => sum + cp.weight_kg, 0);
  const cargoVolume = cargoPlaces.reduce(
    (sum, cp) => sum + (cp.length_mm * cp.width_mm * cp.height_mm) / 1e9,
    0
  );

  // Phase 5d: `items` carries invoice_items-shaped rows (per-invoice
  // supplier positions). `weight_in_kg` is sourced from invoice_items;
  // the legacy quote_items column is dropped in migration 284.
  const weightItems: LogisticsWeightItem[] = items.map((item) => ({
    quantity: item.quantity,
    weight_in_kg:
      (item as unknown as { weight_in_kg: number | null }).weight_in_kg ?? null,
  }));
  const totalWeight = computeTotalWeight(weightItems, cargoPlaces);

  const logisticsCost =
    (invoice.logistics_supplier_to_hub ?? 0) +
    (invoice.logistics_hub_to_customs ?? 0) +
    (invoice.logistics_customs_to_customer ?? 0);

  const hasAnyRoute =
    invoice.logistics_supplier_to_hub != null ||
    invoice.logistics_hub_to_customs != null ||
    invoice.logistics_customs_to_customer != null;

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-muted/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={16} className="shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight size={16} className="shrink-0 text-muted-foreground" />
        )}

        <span className="font-medium text-sm truncate min-w-0">
          {invoice.invoice_number}
        </span>

        <span className="text-sm text-muted-foreground truncate min-w-0">
          {supplierName}
        </span>

        <span className="text-xs text-muted-foreground truncate min-w-0 hidden sm:inline">
          {pickup || "\u2014"} &rarr; {destination}
        </span>

        <span className="text-xs text-muted-foreground tabular-nums shrink-0">
          {hasCargoPlaces ? cargoPlaces.length : (invoice.package_count ?? 0)} мест
        </span>

        <span className="text-xs text-muted-foreground tabular-nums shrink-0">
          {numberFmt.format(totalWeight)} кг
        </span>

        {(hasCargoPlaces ? cargoVolume > 0 : (invoice.total_volume_m3 != null && invoice.total_volume_m3 > 0)) && (
          <span className="text-xs text-muted-foreground tabular-nums shrink-0">
            {numberFmt.format(hasCargoPlaces ? cargoVolume : invoice.total_volume_m3!)} м&sup3;
          </span>
        )}

        <span
          className={cn(
            "ml-auto text-sm font-mono tabular-nums shrink-0",
            hasAnyRoute ? "text-foreground" : "text-muted-foreground"
          )}
        >
          {hasAnyRoute ? numberFmt.format(logisticsCost) : "\u2014"}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-border divide-y divide-border">
          {hasCargoPlaces && (
            <div className="px-4 py-2 bg-muted/30">
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
                <div className="text-xs font-medium text-muted-foreground pt-1 border-t border-border mt-1">
                  Итого: {numberFmt.format(cargoWeight)} кг, {cargoVolume.toFixed(2)} м&sup3;
                </div>
              </div>
            </div>
          )}
          <ProductsSubtable items={items} invoice={invoice} />
          <RouteSegments invoice={invoice} deliveryCity={deliveryCity} />
          <AdditionalExpenses invoiceId={invoice.id} />
        </div>
      )}
    </Card>
  );
}
