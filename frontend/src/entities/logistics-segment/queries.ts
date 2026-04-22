import "server-only";
import { createAdminClient } from "@/shared/lib/supabase/server";

/**
 * logistics-segment entity — per-invoice route segments for Route Constructor.
 *
 * Read via Supabase (server-side, org-scoped + RLS). Shape mirrors the
 * constructor's UI need: each segment carries its from/to locations
 * resolved, plus expenses aggregated client-side (short lists, no N+1 concern).
 *
 * Mutations live in `server-actions.ts` and hit the Python API.
 */

export interface LogisticsSegmentLocationRef {
  id: string;
  country: string;
  iso2?: string;
  city?: string;
  type: "supplier" | "hub" | "customs" | "own_warehouse" | "client";
}

export interface LogisticsSegmentExpense {
  id: string;
  label: string;
  costRub: number;
  days?: number;
  notes?: string;
}

export interface LogisticsSegment {
  id: string;
  invoiceId: string;
  sequenceOrder: number;
  fromLocation?: LogisticsSegmentLocationRef;
  toLocation?: LogisticsSegmentLocationRef;
  label?: string;
  transitDays?: number;
  mainCostRub: number;
  carrier?: string;
  notes?: string;
  expenses: LogisticsSegmentExpense[];
}

interface SegmentRow {
  id: string;
  invoice_id: string;
  sequence_order: number;
  from_location_id: string | null;
  to_location_id: string | null;
  label: string | null;
  transit_days: number | null;
  main_cost_rub: number | string | null;
  carrier: string | null;
  notes: string | null;
  from_location:
    | {
        id: string;
        country: string;
        country_iso2: string | null;
        city: string | null;
        location_type: string | null;
      }
    | null;
  to_location:
    | {
        id: string;
        country: string;
        country_iso2: string | null;
        city: string | null;
        location_type: string | null;
      }
    | null;
  expenses:
    | {
        id: string;
        label: string;
        cost_rub: number | string | null;
        days: number | null;
        notes: string | null;
      }[]
    | null;
}

function coerceType(raw: unknown): LogisticsSegmentLocationRef["type"] {
  const allowed = ["supplier", "hub", "customs", "own_warehouse", "client"] as const;
  return allowed.includes(raw as (typeof allowed)[number])
    ? (raw as (typeof allowed)[number])
    : "hub";
}

function mapLocation(
  l: SegmentRow["from_location"],
): LogisticsSegmentLocationRef | undefined {
  if (!l) return undefined;
  return {
    id: l.id,
    country: l.country,
    iso2: l.country_iso2 ?? undefined,
    city: l.city ?? undefined,
    type: coerceType(l.location_type),
  };
}

function toNumber(v: number | string | null): number {
  if (v == null) return 0;
  return typeof v === "number" ? v : Number(v) || 0;
}

function mapRow(r: SegmentRow): LogisticsSegment {
  return {
    id: r.id,
    invoiceId: r.invoice_id,
    sequenceOrder: r.sequence_order,
    fromLocation: mapLocation(r.from_location),
    toLocation: mapLocation(r.to_location),
    label: r.label ?? undefined,
    transitDays: r.transit_days ?? undefined,
    mainCostRub: toNumber(r.main_cost_rub),
    carrier: r.carrier ?? undefined,
    notes: r.notes ?? undefined,
    expenses: (r.expenses ?? []).map((e) => ({
      id: e.id,
      label: e.label,
      costRub: toNumber(e.cost_rub),
      days: e.days ?? undefined,
      notes: e.notes ?? undefined,
    })),
  };
}

export async function fetchSegmentsForInvoice(
  invoiceId: string,
): Promise<LogisticsSegment[]> {
  const admin = createAdminClient();
  const { data, error } = await admin
    .from("logistics_route_segments")
    .select(
      `
      id, invoice_id, sequence_order,
      from_location_id, to_location_id,
      label, transit_days, main_cost_rub, carrier, notes,
      from_location:locations!logistics_route_segments_from_location_id_fkey (
        id, country, country_iso2, city, location_type
      ),
      to_location:locations!logistics_route_segments_to_location_id_fkey (
        id, country, country_iso2, city, location_type
      ),
      expenses:logistics_segment_expenses (
        id, label, cost_rub, days, notes
      )
    `,
    )
    .eq("invoice_id", invoiceId)
    .order("sequence_order", { ascending: true });

  if (error) {
    // eslint-disable-next-line no-console
    console.error("[fetchSegmentsForInvoice]", error);
    return [];
  }
  return (data ?? []).map(mapRow as (r: unknown) => LogisticsSegment);
}
