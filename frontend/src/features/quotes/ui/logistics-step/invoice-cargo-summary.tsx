"use client";

import { Boxes, MapPin, Package, Ruler, Truck } from "lucide-react";
import type {
  QuoteInvoiceRow,
  QuoteItemRow,
} from "@/entities/quote/queries";
import { cn } from "@/lib/utils";

/**
 * InvoiceCargoSummary — read-only digest of WHAT a logistics route is
 * actually moving, shown above the route constructor on the logistics
 * step.
 *
 * Procurement enters origin + dimensions on the invoice
 * (kvota.invoices.pickup_country, pickup_city, total_weight_kg,
 * total_volume_m3, package_count, length_m/width_m/height_m,
 * supplier_incoterms). Destination is a quote-level concern
 * (kvota.quotes.delivery_country/city/address) and is passed in
 * through the `destination` prop. The cargo digest is derived from
 * `quote_items.composition_selected_invoice_id` — items the buyer
 * picked to ride in this КПП — passed in via `items`.
 *
 * Closes:
 *   - РОЛ Тест 07 #3.3 (origin + dimensions, original release).
 *   - МОЛ Тест row 14 (destination + cargo digest extension).
 *
 * Schema gap (deferred): kvota.invoices does NOT have a
 * `transit_via_turkey` flag or a `pickup_address` column. Those
 * tester-requested fields are tracked separately and require a
 * migration before they can be rendered.
 */

interface Destination {
  country: string | null;
  city: string | null;
  address: string | null;
}

interface InvoiceCargoSummaryProps {
  invoice: QuoteInvoiceRow;
  /**
   * Destination read from the parent quote (delivery_country/city/address).
   * Optional because some legacy quotes never set delivery info.
   */
  destination?: Destination;
  /**
   * All quote items. The component filters to items whose
   * `composition_selected_invoice_id` matches `invoice.id` so the
   * caller doesn't have to pre-filter.
   */
  items?: readonly QuoteItemRow[];
  className?: string;
}

const KG_FMT = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });
const M3_FMT = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });
const M_FMT = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 });

const POSITIONS_PLURAL = new Intl.PluralRules("ru-RU");

function pluralPositions(count: number): string {
  // Russian plural: 1 позиция / 2-4 позиции / 5+ позиций.
  const rule = POSITIONS_PLURAL.select(count);
  if (rule === "one") return "позиция";
  if (rule === "few") return "позиции";
  return "позиций";
}

function joinParts(parts: (string | null | undefined)[]): string | null {
  const cleaned = parts.filter(
    (v): v is string => typeof v === "string" && v.trim().length > 0,
  );
  return cleaned.length === 0 ? null : cleaned.join(", ");
}

function formatDimensions(invoice: QuoteInvoiceRow): string | null {
  const { length_m, width_m, height_m } = invoice;
  if (length_m == null && width_m == null && height_m == null) return null;
  const fmt = (v: number | null) => (v == null ? "—" : M_FMT.format(v));
  return `${fmt(length_m)} × ${fmt(width_m)} × ${fmt(height_m)} м`;
}

function formatCargoDigest(items: readonly QuoteItemRow[]): string | null {
  if (items.length === 0) return null;
  const names = items
    .map((i) => i.product_name?.trim())
    .filter((s): s is string => !!s);
  // Testing 2 row 14 v2: testers (РОЛ/МОЛ/МВЭД) explicitly asked to see
  // ALL item names — the previous "+N" overflow hid most of the cargo.
  // The panel uses `flex flex-wrap`, so a long comma-separated list
  // wraps naturally instead of being truncated.
  const joined = names.join(", ");
  const count = `${items.length} ${pluralPositions(items.length)}`;
  return joined ? `${count}: ${joined}` : count;
}

interface Field {
  icon: React.ComponentType<{
    size?: number;
    strokeWidth?: number;
    "aria-hidden"?: boolean;
  }>;
  label: string;
  value: string;
}

function buildFields(
  invoice: QuoteInvoiceRow,
  destination: Destination | undefined,
  invoiceItems: readonly QuoteItemRow[],
): Field[] {
  const out: Field[] = [];

  const origin = joinParts([invoice.pickup_country, invoice.pickup_city]);
  if (origin) out.push({ icon: MapPin, label: "Откуда", value: origin });

  const dest =
    destination &&
    joinParts([destination.country, destination.city, destination.address]);
  if (dest) out.push({ icon: MapPin, label: "Куда", value: dest });

  const buyerName =
    (invoice.buyer_company as { name?: string } | null)?.name ?? null;
  if (buyerName) out.push({ icon: Truck, label: "Получатель", value: buyerName });

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
  if (dims) out.push({ icon: Ruler, label: "Габариты", value: dims });

  if (invoice.supplier_incoterms) {
    out.push({
      icon: Truck,
      label: "Incoterms",
      value: invoice.supplier_incoterms,
    });
  }

  const digest = formatCargoDigest(invoiceItems);
  if (digest) out.push({ icon: Package, label: "Груз", value: digest });

  return out;
}

export function InvoiceCargoSummary({
  invoice,
  destination,
  items,
  className,
}: InvoiceCargoSummaryProps) {
  const invoiceItems = (items ?? []).filter(
    (it) => it.composition_selected_invoice_id === invoice.id,
  );
  const fields = buildFields(invoice, destination, invoiceItems);

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
          <div key={f.label} className="inline-flex items-center gap-1.5">
            <f.icon size={12} strokeWidth={2} aria-hidden />
            <span className="text-text-muted">{f.label}:</span>
            <span className="font-medium text-text">{f.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
