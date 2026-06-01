"use client";

import { Boxes, Coins, Hash, MapPin, Package, Ruler, Scale, Truck } from "lucide-react";
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
 * Procurement enters origin on the invoice (kvota.invoices.pickup_country,
 * pickup_city, supplier_incoterms) and per-package dimensions in
 * kvota.invoice_cargo_places (weight_kg + length_mm × width_mm × height_mm
 * per box). Destination is a quote-level concern
 * (kvota.quotes.delivery_country/city/address) and is passed in
 * through the `destination` prop. The cargo digest is derived from
 * `quote_items.composition_selected_invoice_id` — items the buyer
 * picked to ride in this КПП — passed in via `items`.
 *
 * The «Мест» count and dimensions list come from
 * `invoice.cargo_places` (Testing 2 row 14 v4) when procurement has
 * filled the per-box table. If it's empty we fall back to the legacy
 * invoice-level `package_count` + `length_m/width_m/height_m` triple so
 * historical КПП still render something.
 *
 * Closes:
 *   - РОЛ Тест 07 #3.3 (origin + dimensions, original release).
 *   - МОЛ Тест row 14 (destination + cargo digest extension).
 *   - Testing 2 row 14 v3 (cargo items as a vertical bullet list).
 *   - Testing 2 row 14 v4 (показывать места и габариты из
 *     invoice_cargo_places, заполняемые procurement на КПП).
 *
 * Schema gap (deferred): kvota.invoices does NOT have a
 * `transit_via_turkey` flag. That tester-requested field is tracked
 * separately and requires a migration before it can be rendered.
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
const MM_FMT = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });

interface CargoPlaceLike {
  weight_kg: number | null;
  length_mm: number | null;
  width_mm: number | null;
  height_mm: number | null;
}

/**
 * Group equal-size boxes so «6 одинаковых мест 800×1200×600» renders as
 * one row instead of six. Grouping key is the L×W×H×weight tuple — if a
 * dimension is NULL it forms its own group (we keep NULL distinct from
 * 0 so the user sees that procurement hasn't filled it yet).
 */
function groupBoxes(
  boxes: readonly CargoPlaceLike[],
): { box: CargoPlaceLike; count: number }[] {
  const groups: { box: CargoPlaceLike; count: number; key: string }[] = [];
  for (const b of boxes) {
    const key = `${b.length_mm ?? "_"}|${b.width_mm ?? "_"}|${b.height_mm ?? "_"}|${b.weight_kg ?? "_"}`;
    const existing = groups.find((g) => g.key === key);
    if (existing) existing.count += 1;
    else groups.push({ box: b, count: 1, key });
  }
  return groups.map(({ box, count }) => ({ box, count }));
}

function formatBoxDimensions(box: CargoPlaceLike): string | null {
  const { length_mm, width_mm, height_mm } = box;
  if (length_mm == null && width_mm == null && height_mm == null) return null;
  const fmt = (v: number | null) => (v == null ? "—" : MM_FMT.format(v));
  return `${fmt(length_mm)}×${fmt(width_mm)}×${fmt(height_mm)} мм`;
}

function renderBoxesList(boxes: readonly CargoPlaceLike[]): React.ReactNode {
  const groups = groupBoxes(boxes);
  return (
    <ul className="list-disc pl-5 text-text">
      {groups.map((g, idx) => {
        const dims = formatBoxDimensions(g.box);
        const weight =
          g.box.weight_kg != null
            ? `${KG_FMT.format(g.box.weight_kg)} кг`
            : null;
        const prefix = g.count > 1 ? `${g.count} × ` : "";
        const parts = [dims, weight].filter(
          (s): s is string => typeof s === "string",
        );
        const body = parts.length === 0 ? "размер не указан" : parts.join(", ");
        return <li key={idx}>{`${prefix}${body}`}</li>;
      })}
    </ul>
  );
}

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

/**
 * Build the per-position label for the cargo digest. Testing 2 row 93:
 * testers asked to surface each position's BRAND alongside its name, so
 * a logistician/customs reviewer recognises «что именно везём» without
 * opening the procurement tab. Rendered as «<Бренд> — <Наименование>»;
 * when brand is empty/null we fall back to just the name (no dangling
 * dash).
 */
function formatCargoItemLabel(item: QuoteItemRow): string | null {
  const name = item.product_name?.trim();
  if (!name) return null;
  const brand = item.brand?.trim();
  return brand ? `${brand} — ${name}` : name;
}

function renderCargoDigest(items: readonly QuoteItemRow[]): React.ReactNode {
  if (items.length === 0) return null;
  const labels = items
    .map(formatCargoItemLabel)
    .filter((s): s is string => !!s);
  const countLabel = `${items.length} ${pluralPositions(items.length)}`;
  // Testing 2 row 14 v3: testers (РОЛ/МОЛ/МВЭД) asked for items as a vertical
  // bullet list — comma-separated wrapping was hard to read once the cargo
  // grew past 3-4 items. Single-text count stays when product names are
  // missing.
  if (labels.length === 0) return countLabel;
  return (
    <div className="flex flex-col gap-0.5">
      <span>{countLabel}:</span>
      <ul className="list-disc pl-5 text-text">
        {labels.map((label, idx) => (
          <li key={`${idx}-${label}`}>{label}</li>
        ))}
      </ul>
    </div>
  );
}

interface Field {
  icon: React.ComponentType<{
    size?: number;
    strokeWidth?: number;
    className?: string;
    "aria-hidden"?: boolean;
  }>;
  label: string;
  value: React.ReactNode;
  /**
   * When true, the field's value is a block-level element (e.g. cargo
   * bullet list). The row uses `items-start` so the icon/label sit at
   * the top instead of vertically centered against a tall block.
   */
  block?: boolean;
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

  // Testing 2 row 14 v4: per-box data from invoice_cargo_places is the
  // source of truth when procurement has filled it. Aggregate weight
  // from boxes; fall back to invoice.total_weight_kg only when boxes
  // are empty.
  const boxes = invoice.cargo_places ?? [];
  const boxesWeightTotal = boxes.reduce(
    (acc, b) => acc + (b.weight_kg ?? 0),
    0,
  );
  const anyBoxWeight = boxes.some((b) => b.weight_kg != null);

  if (boxes.length > 0 && anyBoxWeight) {
    out.push({
      icon: Boxes,
      label: "Вес",
      value: `${KG_FMT.format(boxesWeightTotal)} кг`,
    });
  } else if (invoice.total_weight_kg != null) {
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

  if (boxes.length > 0) {
    out.push({
      icon: Package,
      label: "Мест",
      value: String(boxes.length),
    });
    // Show per-box dimension list only when at least one box has a
    // non-null dimension — a list full of «размер не указан» is noise.
    const anyBoxDims = boxes.some(
      (b) =>
        b.length_mm != null || b.width_mm != null || b.height_mm != null,
    );
    if (anyBoxDims) {
      out.push({
        icon: Ruler,
        label: "Габариты",
        value: renderBoxesList(boxes),
        block: true,
      });
    }
  } else {
    if (invoice.package_count != null) {
      out.push({
        icon: Package,
        label: "Мест",
        value: String(invoice.package_count),
      });
    }
    const dims = formatDimensions(invoice);
    if (dims) out.push({ icon: Ruler, label: "Габариты", value: dims });
  }

  if (invoice.supplier_incoterms) {
    out.push({
      icon: Truck,
      label: "Incoterms",
      value: invoice.supplier_incoterms,
    });
  }

  // Testing 2 row 71 — 4 КПП totals (Валюта / Стоимость / Кол-во / Ед.изм.).
  // All four fields hang off the per-invoice items_aggregate computed in
  // fetchQuoteInvoices. They appear together so the customs/logistics
  // reviewer can sanity-check «что и сколько везём» without opening the
  // procurement step.
  //
  // Gating on `aggregate != null` keeps the empty КП state quiet: an
  // invoice that was created but has no invoice_items yet would otherwise
  // surface its default `currency: "USD"` even though procurement hasn't
  // filled anything (preserves «Закупка ещё не заполнила груз» fallback).
  const aggregate = invoice.items_aggregate ?? null;

  if (aggregate) {
    const aggregateCurrency = aggregate.currency ?? invoice.currency ?? null;

    if (aggregateCurrency) {
      out.push({
        icon: Coins,
        label: "Валюта КПП",
        value: aggregateCurrency,
      });
    }

    if (aggregate.total_amount_original != null) {
      // Show the procurement-side cost in КПП currency. Two-decimal format —
      // money cells follow the same convention as the calc engine output.
      out.push({
        icon: Coins,
        label: "Стоимость",
        value: `${M3_FMT.format(aggregate.total_amount_original)}${aggregateCurrency ? ` ${aggregateCurrency}` : ""}`,
      });
    }

    if (aggregate.total_quantity != null) {
      out.push({
        icon: Hash,
        label: "Кол-во",
        value: KG_FMT.format(aggregate.total_quantity),
      });
    }

    if (aggregate.units?.length) {
      // КПП usually contains a single unit kind; show the literal value.
      // Mixed-unit КП (heterogeneous «шт + кг») drop to «разные» so the
      // reviewer realises the aggregate quantity is unit-less.
      out.push({
        icon: Scale,
        label: "Ед.изм.",
        value: aggregate.units.length === 1 ? aggregate.units[0] : "разные",
      });
    }
  }

  const digest = renderCargoDigest(invoiceItems);
  if (digest)
    out.push({
      icon: Package,
      label: "Груз",
      value: digest,
      block: invoiceItems.length > 0,
    });

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
      <div className="flex flex-wrap items-start gap-x-5 gap-y-2 text-xs">
        {fields.map((f) => (
          <div
            key={f.label}
            className={cn(
              "gap-1.5",
              f.block
                ? "flex items-start"
                : "inline-flex items-center",
            )}
          >
            <f.icon
              size={12}
              strokeWidth={2}
              aria-hidden
              // Nudge the icon down a hair when it sits beside a block
              // value so it visually aligns with the count label.
              className={f.block ? "mt-0.5 shrink-0" : undefined}
            />
            <span className="text-text-muted">{f.label}:</span>
            <span className="font-medium text-text">{f.value}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
