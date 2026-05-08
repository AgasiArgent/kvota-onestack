"use client";

import { Boxes, Package, MapPin, Ruler, Truck } from "lucide-react";
import type { QuoteInvoiceRow } from "@/entities/quote/queries";
import { cn } from "@/lib/utils";

/**
 * InvoiceCargoSummary — read-only digest of WHAT a logistics route is
 * actually moving, shown above the route constructor on the logistics
 * step.
 *
 * Procurement enters this data on the procurement step (origin country
 * + city, total weight & volume, package count, packed dimensions,
 * incoterms). The logistician needs it visible while editing segments
 * because route choice, carrier negotiation and customs filings all
 * depend on it.
 *
 * Source: kvota.invoices columns — pickup_country, pickup_city,
 * total_weight_kg, total_volume_m3, package_count, length_m, width_m,
 * height_m, supplier_incoterms.
 *
 * Closes РОЛ Тест 07 #3.3 (cluster L-A): «КПП expanded view не
 * отображает груз / габариты / откуда-куда».
 */

interface InvoiceCargoSummaryProps {
  invoice: QuoteInvoiceRow;
  className?: string;
}

const KG_FMT = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 1,
});
const M3_FMT = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 2,
});
const M_FMT = new Intl.NumberFormat("ru-RU", {
  maximumFractionDigits: 2,
});

function formatOrigin(invoice: QuoteInvoiceRow): string | null {
  const parts = [invoice.pickup_country, invoice.pickup_city].filter(
    (v): v is string => typeof v === "string" && v.trim().length > 0,
  );
  if (parts.length === 0) return null;
  return parts.join(", ");
}

function formatDimensions(invoice: QuoteInvoiceRow): string | null {
  const { length_m, width_m, height_m } = invoice;
  if (length_m == null && width_m == null && height_m == null) return null;
  const fmt = (v: number | null) => (v == null ? "—" : M_FMT.format(v));
  return `${fmt(length_m)} × ${fmt(width_m)} × ${fmt(height_m)} м`;
}

interface Field {
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; "aria-hidden"?: boolean }>;
  label: string;
  value: string;
}

function buildFields(invoice: QuoteInvoiceRow): Field[] {
  const out: Field[] = [];

  const origin = formatOrigin(invoice);
  if (origin) {
    out.push({ icon: MapPin, label: "Откуда", value: origin });
  }

  const buyerName =
    (invoice.buyer_company as { name?: string } | null)?.name ?? null;
  if (buyerName) {
    out.push({ icon: Truck, label: "Получатель", value: buyerName });
  }

  if (invoice.total_weight_kg != null) {
    out.push({
      icon: Boxes,
      label: "Вес",
      value: `${KG_FMT.format(invoice.total_weight_kg)} кг`,
    });
  }
  if (invoice.total_volume_m3 != null) {
    out.push({
      icon: Boxes,
      label: "Объём",
      value: `${M3_FMT.format(invoice.total_volume_m3)} м³`,
    });
  }
  if (invoice.package_count != null) {
    out.push({
      icon: Package,
      label: "Мест",
      value: String(invoice.package_count),
    });
  }
  const dims = formatDimensions(invoice);
  if (dims) {
    out.push({ icon: Ruler, label: "Габариты", value: dims });
  }
  if (invoice.supplier_incoterms) {
    out.push({
      icon: Truck,
      label: "Incoterms",
      value: invoice.supplier_incoterms,
    });
  }

  return out;
}

export function InvoiceCargoSummary({
  invoice,
  className,
}: InvoiceCargoSummaryProps) {
  const fields = buildFields(invoice);

  if (fields.length === 0) {
    return (
      <div
        className={cn(
          "rounded-lg border border-dashed border-border-light bg-card px-4 py-3 text-xs text-text-muted",
          className,
        )}
        data-testid="invoice-cargo-summary-empty"
      >
        Закупка ещё не заполнила груз и габариты по этому КПП.
      </div>
    );
  }

  return (
    <section
      aria-label="Груз и габариты КПП"
      data-testid="invoice-cargo-summary"
      className={cn(
        "rounded-lg border border-border-light bg-card px-4 py-3",
        className,
      )}
    >
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs">
        {fields.map((f) => (
          <div
            key={f.label}
            className="inline-flex items-center gap-1.5"
          >
            <f.icon size={12} strokeWidth={2} aria-hidden />
            <span className="text-text-muted">{f.label}:</span>
            <span className="font-medium text-text">{f.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
