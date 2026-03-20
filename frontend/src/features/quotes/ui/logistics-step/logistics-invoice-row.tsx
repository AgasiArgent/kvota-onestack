"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";
import { ProductsSubtable } from "./products-subtable";
import { RouteSegments } from "./route-segments";
import { AdditionalExpenses } from "./additional-expenses";

const numberFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

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

  const supplierName =
    (invoice.supplier as { name: string } | null)?.name ?? "\u2014";

  const pickup = [invoice.pickup_city, invoice.pickup_country]
    .filter(Boolean)
    .join(", ");
  const destination = deliveryCity ?? "\u2014";

  const totalWeight = items.reduce(
    (sum, item) => sum + (item.weight_in_kg ?? 0) * item.quantity,
    0
  );

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
          {invoice.package_count ?? 0} мест
        </span>

        <span className="text-xs text-muted-foreground tabular-nums shrink-0">
          {numberFmt.format(totalWeight)} кг
        </span>

        {invoice.total_volume_m3 != null && invoice.total_volume_m3 > 0 && (
          <span className="text-xs text-muted-foreground tabular-nums shrink-0">
            {numberFmt.format(invoice.total_volume_m3)} м³
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
          <ProductsSubtable items={items} invoice={invoice} />
          <RouteSegments invoice={invoice} deliveryCity={deliveryCity} />
          <AdditionalExpenses invoiceId={invoice.id} />
        </div>
      )}
    </Card>
  );
}
