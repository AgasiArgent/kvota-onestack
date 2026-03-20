"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { updateInvoiceLogistics } from "@/entities/quote/mutations";
import type { QuoteInvoiceRow } from "@/entities/quote/queries";

const CURRENCIES = ["USD", "EUR", "CNY", "RUB"] as const;

interface Segment {
  key: string;
  label: string;
  route: string;
  price: number | null;
  currency: string;
  days: number | null;
  priceColumn: string;
  currencyColumn: string;
}

function buildSegments(invoice: QuoteInvoiceRow, deliveryCity: string | null): Segment[] {
  const pickup = [invoice.pickup_city, invoice.pickup_country]
    .filter(Boolean)
    .join(", ");
  const destination = deliveryCity ?? "Клиент";

  return [
    {
      key: "supplier_to_hub",
      label: "Поставщик \u2192 Хаб",
      route: pickup ? `${pickup} \u2192 Хаб` : "\u2014",
      price: invoice.logistics_supplier_to_hub ?? null,
      currency: invoice.logistics_supplier_to_hub_currency ?? "USD",
      days: null,
      priceColumn: "logistics_supplier_to_hub",
      currencyColumn: "logistics_supplier_to_hub_currency",
    },
    {
      key: "hub_to_customs",
      label: "Хаб \u2192 Таможня",
      route: "Хаб \u2192 Таможня",
      price: invoice.logistics_hub_to_customs ?? null,
      currency: invoice.logistics_hub_to_customs_currency ?? "USD",
      days: null,
      priceColumn: "logistics_hub_to_customs",
      currencyColumn: "logistics_hub_to_customs_currency",
    },
    {
      key: "customs_to_customer",
      label: "Таможня \u2192 Клиент",
      route: `Таможня \u2192 ${destination}`,
      price: invoice.logistics_customs_to_customer ?? null,
      currency: invoice.logistics_customs_to_customer_currency ?? "USD",
      days: null,
      priceColumn: "logistics_customs_to_customer",
      currencyColumn: "logistics_customs_to_customer_currency",
    },
  ];
}

interface RouteSegmentsProps {
  invoice: QuoteInvoiceRow;
  deliveryCity: string | null;
}

export function RouteSegments({ invoice, deliveryCity }: RouteSegmentsProps) {
  const router = useRouter();
  const initial = buildSegments(invoice, deliveryCity);
  const [segments, setSegments] = useState<Segment[]>(initial);

  function handleChange(index: number, field: keyof Segment, value: string) {
    setSegments((prev) => {
      const updated = [...prev];
      const seg = { ...updated[index] };

      if (field === "price") {
        const parsed = parseFloat(value);
        seg.price = isNaN(parsed) ? null : parsed;
      } else if (field === "days") {
        const parsed = parseInt(value, 10);
        seg.days = isNaN(parsed) ? null : parsed;
      } else if (field === "currency") {
        seg.currency = value;
      }

      updated[index] = seg;
      return updated;
    });
  }

  const saveToDb = useCallback(
    async (seg: Segment, field: "price" | "currency" | "days") => {
      const updates: Record<string, unknown> = {};

      if (field === "price") {
        updates[seg.priceColumn] = seg.price;
      } else if (field === "currency") {
        updates[seg.currencyColumn] = seg.currency;
      } else if (field === "days") {
        // Days are stored at the invoice level as logistics_total_days
        // Recalculate total days from all segments
        const totalDays = segments.reduce(
          (sum, s) => sum + (s.days ?? 0),
          0
        );
        updates.logistics_total_days = totalDays > 0 ? totalDays : null;
      }

      try {
        await updateInvoiceLogistics(invoice.id, updates);
        router.refresh();
      } catch {
        toast.error("Не удалось сохранить маршрут");
      }
    },
    [invoice.id, segments, router]
  );

  function handleBlur(index: number, field: "price" | "currency" | "days") {
    const seg = segments[index];
    saveToDb(seg, field);
  }

  return (
    <div>
      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-2 border-b border-border bg-muted/30">
        Маршрут
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="text-left font-medium px-4 py-1.5 w-40">Сегмент</th>
              <th className="text-left font-medium px-2 py-1.5">Маршрут</th>
              <th className="text-right font-medium px-2 py-1.5 w-28">Цена</th>
              <th className="text-left font-medium px-2 py-1.5 w-20">Валюта</th>
              <th className="text-right font-medium px-2 py-1.5 w-20">Дни</th>
            </tr>
          </thead>
          <tbody>
            {segments.map((seg, idx) => (
              <tr key={seg.key} className="border-b border-border/50">
                <td className="px-4 py-1 text-muted-foreground text-xs">
                  {seg.label}
                </td>
                <td className="px-2 py-1 text-xs text-muted-foreground">
                  {seg.route}
                </td>
                <td className="px-2 py-1">
                  <input
                    type="number"
                    step="0.01"
                    className="w-full h-7 px-1.5 text-right font-mono text-sm border border-border rounded bg-transparent focus:outline-none focus:border-ring focus:ring-1 focus:ring-ring/50 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    value={seg.price ?? ""}
                    onChange={(e) => handleChange(idx, "price", e.target.value)}
                    onBlur={() => handleBlur(idx, "price")}
                    placeholder="0.00"
                  />
                </td>
                <td className="px-2 py-1">
                  <select
                    className="w-full h-7 px-1 text-xs border border-border rounded bg-transparent focus:outline-none focus:border-ring focus:ring-1 focus:ring-ring/50 cursor-pointer"
                    value={seg.currency}
                    onChange={(e) => {
                      handleChange(idx, "currency", e.target.value);
                      // Save immediately on currency change (no blur needed for selects)
                      const updated = [...segments];
                      const s = { ...updated[idx], currency: e.target.value };
                      updated[idx] = s;
                      setSegments(updated);
                      saveToDb(s, "currency");
                    }}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-1">
                  <input
                    type="number"
                    className="w-full h-7 px-1.5 text-right font-mono text-sm border border-border rounded bg-transparent focus:outline-none focus:border-ring focus:ring-1 focus:ring-ring/50 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    value={seg.days ?? ""}
                    onChange={(e) => handleChange(idx, "days", e.target.value)}
                    onBlur={() => handleBlur(idx, "days")}
                    placeholder="0"
                  />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="border-t border-border">
              <td colSpan={2} className="px-4 py-1.5 text-xs font-medium text-muted-foreground">
                Всего дней
              </td>
              <td />
              <td />
              <td className="px-2 py-1.5 text-right font-mono text-sm font-medium">
                {invoice.logistics_total_days ?? "\u2014"}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}
