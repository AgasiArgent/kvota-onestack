"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import type {
  QuoteDetailRow,
  QuoteInvoiceRow,
  QuoteItemRow,
} from "@/entities/quote/queries";
import { createClient } from "@/shared/lib/supabase/client";
import type { LocationOption, LocationType } from "@/entities/location";
import type {
  LogisticsSegment,
  SegmentCurrency,
} from "@/entities/logistics-segment";
import {
  SEGMENT_CURRENCIES,
  completeLogistics,
} from "@/entities/logistics-segment";
import type { LogisticsTemplate } from "@/entities/logistics-template";
import type { FxRateMap } from "@/shared/lib/fx-convert";
import { RouteConstructor } from "@/features/route-constructor";
import {
  InvoiceTabs,
  type InvoiceTabItem,
  type InvoiceTabStatus,
} from "@/features/quotes/ui/invoice-tabs";
import { EntityNotesPanel } from "@/entities/entity-note";
import type { EntityNoteCardData } from "@/entities/entity-note/ui/entity-note-card";
import { LogisticsActionBar } from "./logistics-action-bar";
import { InvoiceCargoSummary } from "./invoice-cargo-summary";

const COMPLETE_LOGISTICS_ROLES = new Set([
  "logistics",
  "head_of_logistics",
  "head_of_customs",
  "admin",
]);

/**
 * LogisticsStep — thin wrapper around the RouteConstructor per invoice.
 *
 * A quote may carry multiple invoices (ТЗ §3.1); logistics is priced at
 * the invoice level, so we render an invoice switcher on top and the
 * route constructor below. All route data (segments, locations,
 * templates) is loaded client-side through the Supabase browser client
 * — RLS restricts rows to the caller's org.
 *
 * Mutations flow through @/entities/logistics-segment (server actions).
 * They revalidate the quote path; we then reload the client cache from
 * Supabase on each change via a refreshTick so the optimistic UI picks
 * up the new canonical state.
 */

interface LogisticsStepProps {
  quote: QuoteDetailRow;
  invoices: QuoteInvoiceRow[];
  /**
   * All quote items. Forwarded to InvoiceCargoSummary so the cargo
   * digest can show item count + names per КПП (МОЛ Тест row 14).
   */
  items?: readonly QuoteItemRow[];
  userId?: string;
  userRoles?: string[];
  quoteNotes?: EntityNoteCardData[];
}

// Narrow shape returned by the `logistics_route_segments` query below.
// We cast here because the new tables are not yet in generated db types.
// from/to_location_id are non-nullable in the DB (migration 288:26-27); a
// previous version of this interface marked them nullable, which masked an
// API/UX bug where segments were created without locations and got a 500.
interface SegmentRowShape {
  id: string;
  invoice_id: string;
  sequence_order: number;
  from_location_id: string;
  to_location_id: string;
  label: string | null;
  transit_days: number | null;
  main_cost_rub: number | string | null;
  /** Added by m309. Falls back to 'RUB' for legacy rows. */
  currency_code: string | null;
  carrier: string | null;
  notes: string | null;
}

interface LocationRowShape {
  id: string;
  country: string;
  city: string | null;
  location_type: string | null;
}

interface ExpenseRowShape {
  id: string;
  segment_id: string;
  label: string;
  cost_rub: number | string | null;
  /** Added by m309. Falls back to 'RUB' for legacy rows. */
  currency_code: string | null;
  days: number | null;
  notes: string | null;
}

interface TemplateRowShape {
  id: string;
  name: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
}

interface TemplateSegmentRowShape {
  id: string;
  template_id: string;
  sequence_order: number;
  from_location_type: string;
  to_location_type: string;
  default_label: string | null;
  default_days: number | null;
  /** Optional concrete location FKs (РОЛ Тест 07 #3.5, m309). */
  from_location_id: string | null;
  to_location_id: string | null;
}

const ALLOWED_TYPES: readonly LocationType[] = [
  "supplier",
  "hub",
  "customs",
  "own_warehouse",
  "client",
];

function coerceType(raw: unknown): LocationType {
  return ALLOWED_TYPES.includes(raw as LocationType)
    ? (raw as LocationType)
    : "hub";
}

function toNumber(v: number | string | null | undefined): number {
  if (v == null) return 0;
  return typeof v === "number" ? v : Number(v) || 0;
}

function coerceCurrency(raw: string | null | undefined): SegmentCurrency {
  if (!raw) return "RUB";
  const upper = raw.toUpperCase();
  return (SEGMENT_CURRENCIES as readonly string[]).includes(upper)
    ? (upper as SegmentCurrency)
    : "RUB";
}

export function LogisticsStep({
  quote,
  invoices,
  items,
  userId,
  userRoles,
  quoteNotes = [],
}: LogisticsStepProps) {
  const [activeInvoiceId, setActiveInvoiceId] = useState<string | null>(
    invoices[0]?.id ?? null,
  );
  const [segmentsByInvoice, setSegmentsByInvoice] = useState<
    Map<string, LogisticsSegment[]>
  >(new Map());
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [templates, setTemplates] = useState<LogisticsTemplate[]>([]);
  // FX rates: foreign-currency → RUB, used by RouteTotalsCard (3.7).
  const [ratesToRub, setRatesToRub] = useState<FxRateMap>({});
  // Testing 2 row 80 — count of invoice_items on this quote whose
  // purchase_price_original is NULL or <= 0. While > 0 the
  // «Завершить логистику» button is disabled, matching the backend gate
  // in api/logistics.complete. We hold this client-side instead of
  // re-deriving from `items` because the truth lives on invoice_items
  // (per-supplier line), not quote_items (per-cart line).
  const [unpricedInvoiceItemsCount, setUnpricedInvoiceItemsCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [completing, startCompleting] = useTransition();
  const router = useRouter();
  // Refresh tick — incremented by RouteConstructor after each successful
  // server mutation. Drives the Supabase data reload below; without it
  // `router.refresh()` re-runs Server Components but never re-fires this
  // client-side useEffect (its deps don't change), so newly created /
  // updated / deleted segments only appeared after a hard reload
  // (Testing 2 row 30 — "сегмент добавляется только после обновления").
  const [refreshTick, setRefreshTick] = useState(0);

  const canCompleteLogistics =
    userRoles?.some((r) => COMPLETE_LOGISTICS_ROLES.has(r)) ?? false;

  const activeInvoice = useMemo(
    () => invoices.find((i) => i.id === activeInvoiceId) ?? null,
    [invoices, activeInvoiceId],
  );

  function handleCompleteLogistics() {
    if (!activeInvoiceId) return;
    startCompleting(async () => {
      try {
        await completeLogistics({
          invoice_id: activeInvoiceId,
          revalidate_path: `/quotes/${quote.id}`,
        });
        toast.success("Логистика по инвойсу завершена");
        router.refresh();
      } catch (err) {
        toast.error(
          err instanceof Error
            ? err.message
            : "Не удалось завершить логистику",
        );
      }
    });
  }

  // Stable key derived from invoice ids. The `invoices` prop is a fresh
  // array reference on every parent render (server data, polling timers,
  // unrelated state updates), so we cannot use it directly as an effect
  // dep without re-running the network load on every render — which
  // produces a "remount" feel mid-typing (РОЛ Тест 07 #3.6, cluster L-A).
  const invoiceIdsKey = useMemo(
    () => invoices.map((i) => i.id).join(","),
    [invoices],
  );

  // Re-pick active invoice if the list changed (id-based, not ref-based)
  useEffect(() => {
    setActiveInvoiceId((prev) => {
      if (prev && invoices.some((i) => i.id === prev)) return prev;
      return invoices[0]?.id ?? null;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- invoiceIdsKey is the canonical dep; `invoices` itself is unstable
  }, [invoiceIdsKey]);

  // Load data — locations, templates (once), segments (per active invoice)
  useEffect(() => {
    // `sb` is cast to any because the new logistics-route-* tables are not
    // yet in the generated Database types (migrations land in a sibling PR).
    // Once `npm run db:types` regenerates, the cast can be removed.
    const sb = createClient() as unknown as {
      from: (table: string) => {
        select: (cols: string) => {
          eq: (...args: unknown[]) => unknown;
          in: (...args: unknown[]) => unknown;
          order: (...args: unknown[]) => unknown;
        };
      };
    };
    const supabase = sb as unknown as {
      from: (table: string) => any; // eslint-disable-line @typescript-eslint/no-explicit-any
    };
    let cancelled = false;
    const orgId = quote.organization_id;
    setLoading(true);

    async function load() {
      const invoiceIds = invoices.map((i) => i.id);

      const [
        locationsRes,
        templatesRes,
        templateSegmentsRes,
        segmentsRes,
        expensesRes,
        ratesRes,
        invoiceItemsPricingRes,
      ] = await Promise.all([
        // Locations — all types, org-scoped
        supabase
          .from("locations")
          .select("id, country, city, location_type")
          .eq("organization_id", orgId)
          .order("country", { ascending: true })
          .order("city", { ascending: true, nullsFirst: true }),
        // Templates
        supabase
          .from("logistics_route_templates")
          .select("id, name, description, created_by, created_at")
          .eq("organization_id", orgId)
          .order("name", { ascending: true }),
        // Template segments — fetch all for this org's templates (small table)
        supabase
          .from("logistics_route_template_segments")
          .select(
            "id, template_id, sequence_order, from_location_type, to_location_type, default_label, default_days, from_location_id, to_location_id",
          ),
        // Segments — only for the loaded quote's invoices
        invoiceIds.length > 0
          ? supabase
              .from("logistics_route_segments")
              .select(
                "id, invoice_id, sequence_order, from_location_id, to_location_id, label, transit_days, main_cost_rub, currency_code, carrier, notes",
              )
              .in("invoice_id", invoiceIds)
              .order("sequence_order", { ascending: true })
          : { data: [], error: null },
        // Expenses — joined via segment_id in a second hop
        invoiceIds.length > 0
          ? supabase
              .from("logistics_segment_expenses")
              .select(
                "id, segment_id, label, cost_rub, currency_code, days, notes",
              )
          : { data: [], error: null },
        // FX rates: most-recent foreign→RUB rates for currencies the
        // segment editor allows. Pulled from kvota.exchange_rates which
        // is an org-agnostic CBR cache (services/currency_service.py).
        // RUB is excluded — it's the base currency (implicit 1.0 in fx-convert).
        supabase
          .from("exchange_rates")
          .select("from_currency, rate, fetched_at")
          .eq("to_currency", "RUB")
          .in(
            "from_currency",
            SEGMENT_CURRENCIES.filter((c) => c !== "RUB"),
          )
          .order("fetched_at", { ascending: false })
          .limit(20),
        // Testing 2 row 80 — pricing gate. Pull the minimum columns
        // needed to count invoice_items whose purchase_price_original is
        // still NULL or <= 0 across ALL of this quote's invoices. The
        // server enforces the same rule (api/logistics.complete returns
        // 409 UNPRICED_INVOICE_ITEMS) — this client-side count exists so
        // we can disable the button + show "Осталось проценить N КПП"
        // without first making the user click and parse a toast.
        invoiceIds.length > 0
          ? supabase
              .from("invoice_items")
              .select("id, purchase_price_original")
              .in("invoice_id", invoiceIds)
          : { data: [], error: null },
      ]);

      if (cancelled) return;

      // Build locations
      const locs: LocationOption[] = (
        (locationsRes.data ?? []) as unknown as LocationRowShape[]
      ).map((l) => ({
        id: l.id,
        country: l.country,
        city: l.city ?? undefined,
        type: coerceType(l.location_type),
      }));
      const locationById = new Map(locs.map((l) => [l.id, l]));

      // Build expenses by segment_id
      const expensesBySegment = new Map<
        string,
        Array<{
          id: string;
          label: string;
          costRub: number;
          currencyCode: SegmentCurrency;
          days?: number;
          notes?: string;
        }>
      >();
      for (const e of (expensesRes.data ?? []) as unknown as ExpenseRowShape[]) {
        const list = expensesBySegment.get(e.segment_id) ?? [];
        list.push({
          id: e.id,
          label: e.label,
          costRub: toNumber(e.cost_rub),
          currencyCode: coerceCurrency(e.currency_code),
          days: e.days ?? undefined,
          notes: e.notes ?? undefined,
        });
        expensesBySegment.set(e.segment_id, list);
      }

      // Build segments by invoice
      const byInvoice = new Map<string, LogisticsSegment[]>();
      for (const row of (segmentsRes.data ?? []) as unknown as SegmentRowShape[]) {
        const fromLoc = row.from_location_id
          ? locationById.get(row.from_location_id)
          : undefined;
        const toLoc = row.to_location_id
          ? locationById.get(row.to_location_id)
          : undefined;
        const list = byInvoice.get(row.invoice_id) ?? [];
        list.push({
          id: row.id,
          invoiceId: row.invoice_id,
          sequenceOrder: row.sequence_order,
          fromLocation: fromLoc
            ? {
                id: fromLoc.id,
                country: fromLoc.country,
                iso2: fromLoc.iso2,
                city: fromLoc.city,
                type: fromLoc.type,
              }
            : undefined,
          toLocation: toLoc
            ? {
                id: toLoc.id,
                country: toLoc.country,
                iso2: toLoc.iso2,
                city: toLoc.city,
                type: toLoc.type,
              }
            : undefined,
          label: row.label ?? undefined,
          transitDays: row.transit_days ?? undefined,
          mainCostRub: toNumber(row.main_cost_rub),
          currencyCode: coerceCurrency(row.currency_code),
          carrier: row.carrier ?? undefined,
          notes: row.notes ?? undefined,
          expenses: expensesBySegment.get(row.id) ?? [],
        });
        byInvoice.set(row.invoice_id, list);
      }
      // Ensure stable order
      for (const list of byInvoice.values()) {
        list.sort((a, b) => a.sequenceOrder - b.sequenceOrder);
      }

      // Build templates with segments
      const templateRows = (templatesRes.data ?? []) as unknown as TemplateRowShape[];
      const templateSegmentRows = (templateSegmentsRes.data ?? []) as unknown as TemplateSegmentRowShape[];
      const templateSegmentsById = new Map<string, TemplateSegmentRowShape[]>();
      for (const s of templateSegmentRows) {
        const list = templateSegmentsById.get(s.template_id) ?? [];
        list.push(s);
        templateSegmentsById.set(s.template_id, list);
      }
      const tmpls: LogisticsTemplate[] = templateRows.map((t) => ({
        id: t.id,
        name: t.name,
        description: t.description ?? undefined,
        createdBy: t.created_by ?? undefined,
        createdAt: t.created_at,
        segments: (templateSegmentsById.get(t.id) ?? [])
          .sort((a, b) => a.sequence_order - b.sequence_order)
          .map((s) => ({
            id: s.id,
            sequenceOrder: s.sequence_order,
            fromLocationType: coerceType(s.from_location_type),
            toLocationType: coerceType(s.to_location_type),
            defaultLabel: s.default_label ?? undefined,
            defaultDays: s.default_days ?? undefined,
            fromLocationId: s.from_location_id ?? undefined,
            toLocationId: s.to_location_id ?? undefined,
          })),
      }));

      // Build foreign-currency → RUB rate map (latest per currency).
      const rates: Record<string, number> = {};
      for (const r of (ratesRes.data ?? []) as Array<{
        from_currency: string;
        rate: number | string | null;
      }>) {
        const code = r.from_currency?.toUpperCase();
        if (!code || code in rates) continue; // first row is most recent
        const numeric = toNumber(r.rate);
        if (numeric > 0) rates[code] = numeric;
      }

      // Pricing gate count (Testing 2 row 80). Treat NULL, 0, and any
      // non-numeric junk as "unpriced" — mirrors the server-side
      // ``_is_priced`` helper in api/logistics.py.
      const pricingRows =
        (invoiceItemsPricingRes.data ?? []) as Array<{
          id: string;
          purchase_price_original: number | string | null;
        }>;
      const unpricedCount = pricingRows.reduce((acc, row) => {
        const raw = row.purchase_price_original;
        if (raw == null) return acc + 1;
        const numeric = typeof raw === "number" ? raw : Number(raw);
        return Number.isFinite(numeric) && numeric > 0 ? acc : acc + 1;
      }, 0);

      setLocations(locs);
      setTemplates(tmpls);
      setSegmentsByInvoice(byInvoice);
      setRatesToRub(rates);
      setUnpricedInvoiceItemsCount(unpricedCount);
      setLoading(false);
    }

    load().catch((err) => {
      if (cancelled) return;
      console.error("[LogisticsStep] failed to load data", err);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- invoiceIdsKey is stable when invoice IDs unchanged; `invoices` ref changes every parent render
  }, [invoiceIdsKey, quote.organization_id, refreshTick]);

  const tabItems: InvoiceTabItem[] = useMemo(
    () =>
      invoices.map((inv) => {
        const supplier =
          (inv.supplier as { name: string } | null)?.name ?? null;
        const status: InvoiceTabStatus = inv.logistics_completed_at
          ? "completed"
          : inv.logistics_assigned_at
            ? "in_progress"
            : "pending";
        const segs = segmentsByInvoice.get(inv.id) ?? [];
        const subLabel =
          segs.length > 0
            ? `${segs.length} ${segs.length === 1 ? "сегмент" : "сегментов"}`
            : undefined;
        return {
          id: inv.id,
          displayName: supplier
            ? `${inv.invoice_number} · ${supplier}`
            : inv.invoice_number,
          subLabel,
          status,
        };
      }),
    [invoices, segmentsByInvoice],
  );

  if (invoices.length === 0) {
    return (
      <div className="flex-1 min-w-0 p-6">
        <div className="rounded-lg border border-dashed border-border-light bg-card px-6 py-12 text-center">
          <p className="text-sm text-text-muted">
            Нет инвойсов для логистики. Сначала завершите закупку.
          </p>
        </div>
      </div>
    );
  }

  const activeSegments = activeInvoiceId
    ? (segmentsByInvoice.get(activeInvoiceId) ?? [])
    : [];

  return (
    <div className="flex-1 min-w-0 flex flex-col gap-4 p-6">
      {invoices.length > 1 && (
        <InvoiceTabs
          invoices={tabItems}
          activeInvoiceId={activeInvoiceId ?? tabItems[0].id}
          onInvoiceChange={setActiveInvoiceId}
        />
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2
            size={20}
            strokeWidth={2}
            className="animate-spin text-text-muted"
            aria-hidden
          />
          <span className="ml-2 text-sm text-text-muted">Загрузка…</span>
        </div>
      ) : activeInvoiceId && activeInvoice ? (
        <>
          <LogisticsActionBar
            segments={activeSegments}
            alreadyCompleted={!!activeInvoice.logistics_completed_at}
            needsReview={!!activeInvoice.logistics_needs_review_since}
            canEdit={canCompleteLogistics}
            completing={completing}
            onComplete={handleCompleteLogistics}
            displayCurrency={quote.currency ?? "RUB"}
            fxRates={ratesToRub}
            unpricedInvoiceItemsCount={unpricedInvoiceItemsCount}
            // Testing 2 row 44 — under supplier-delivers terms the first
            // segment's cost is locked to 0; the completion gate must exempt
            // it so logistics can still be completed.
            supplierIncoterms={activeInvoice.supplier_incoterms ?? null}
          />
          {/* Cargo digest from procurement — РОЛ Тест 07 #3.3 + МОЛ Тест row 14. */}
          <InvoiceCargoSummary
            invoice={activeInvoice}
            destination={{
              country: quote.delivery_country ?? null,
              city: quote.delivery_city ?? null,
              address: quote.delivery_address ?? null,
            }}
            items={items}
          />
          <RouteConstructor
            key={activeInvoiceId}
            invoiceId={activeInvoiceId}
            orgId={quote.organization_id}
            initialSegments={activeSegments}
            locations={locations}
            templates={templates}
            revalidatePath={`/quotes/${quote.id}`}
            pickupHint={{
              country: activeInvoice.pickup_country ?? null,
              city: activeInvoice.pickup_city ?? null,
            }}
            // Testing 2 row 44 — forwards supplier_incoterms so the route
            // constructor can lock the first segment's cost when the
            // supplier covers that leg (D-terms / C-terms).
            supplierIncoterms={activeInvoice.supplier_incoterms ?? null}
            displayCurrency={quote.currency ?? "RUB"}
            ratesToRub={ratesToRub}
            onMutation={() => setRefreshTick((t) => t + 1)}
          />
        </>
      ) : null}

      {userId && (
        <EntityNotesPanel
          entityType="quote"
          entityId={quote.id}
          initialNotes={quoteNotes}
          currentUser={{ id: userId, roles: userRoles ?? [] }}
          title="Заметки логистов по КП"
          defaultVisibleTo={["logistics", "head_of_logistics", "head_of_customs", "sales", "procurement"]}
        />
      )}
    </div>
  );
}
