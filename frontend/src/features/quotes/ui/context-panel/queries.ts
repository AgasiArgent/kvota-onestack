import { createClient, createAdminClient } from "@/shared/lib/supabase/server";
import type { LocationOption } from "@/entities/location/lib/format";
import type { LocationType } from "@/entities/location/ui/location-chip";
import type { SalesChecklist } from "./sales-checklist-block";

const ALLOWED_LOCATION_TYPES: readonly LocationType[] = [
  "supplier",
  "hub",
  "customs",
  "own_warehouse",
  "client",
];

function normaliseLocationType(raw: string | null): LocationType {
  return ALLOWED_LOCATION_TYPES.includes(raw as LocationType)
    ? (raw as LocationType)
    : "supplier";
}

export interface ContextPanelParticipant {
  id: string;
  actor_id: string;
  actor_role: string;
  actor_name: string;
  from_status: string;
  to_status: string;
  created_at: string | null;
}

export interface ContextPanelSalesManager {
  id: string;
  full_name: string;
  phone: string | null;
  email: string | null;
}

export interface ContextPanelContact {
  name: string;
  last_name: string | null;
  patronymic: string | null;
  phone: string | null;
  email: string | null;
}

/**
 * Domain-specific assignee on the quote (МОЛ / МОТ) — sourced from the
 * per-invoice assignment columns (`invoices.assigned_logistics_user` /
 * `assigned_customs_user`) introduced for SLA tracking. A quote may carry
 * several invoices (КПП), each assignable independently; we deduplicate by
 * user_id and surface the earliest assignment timestamp so the Participants
 * inf-panel mirrors what `head_of_logistics` / `head_of_customs` see in their
 * workspace tables. РОЛ Тест 07 → 3.1 (МОЛ missing) + 4.1 (МОТ missing).
 */
export interface ContextPanelDomainAssignee {
  user_id: string;
  full_name: string;
  /**
   * Earliest assignment timestamp across all invoices that share this user
   * (a single МОЛ may cover several КПП — we surface the first attach).
   */
  assigned_at: string | null;
}

export interface QuoteContextData {
  salesChecklist: SalesChecklist | null;
  contactPerson: ContextPanelContact | null;
  salesManager: ContextPanelSalesManager | null;
  participants: ContextPanelParticipant[];
  /**
   * Distinct МОЗ assignees on this quote's items
   * (`quote_items.assigned_procurement_user`).
   *
   * Testing 2 row 2 (FB-260513-100338-a778): the «Участники» info panel was
   * missing the procurement responsible — only МОЛ + МОТ surfaced. МОЗ is the
   * single source of truth on `quote_items.assigned_procurement_user`
   * (per `.kiro/specs/procurement-users-single-source/`); we deduplicate by
   * user_id.
   *
   * Testing 2 row 79 (FB-260522): «когда привязали» is now sourced from the
   * `status_history` row that records the brand-slice routing moment
   * (reason = 'auto: all items routed'). We map each МОЗ user to the brands
   * they cover on the quote and take the earliest routed timestamp across
   * those brands. Falls back to the user's own earliest workflow_transitions
   * row when no routing event exists for any of their brands (legacy quotes /
   * partially routed slices).
   */
  procurementAssignees: ContextPanelDomainAssignee[];
  /** Distinct МОЛ assignees on this quote's invoices (РОЛ Тест 07 / 3.1). */
  logisticsAssignees: ContextPanelDomainAssignee[];
  /** Distinct МОТ assignees on this quote's invoices (РОЛ Тест 07 / 4.1). */
  customsAssignees: ContextPanelDomainAssignee[];
  /**
   * Distinct pickup locations referenced by this quote's items.
   *
   * Testing 2 row 78 (user override: «78 на /quotes не на /locations!»): the
   * quote ↔ location relationship must be VISIBLE on the quote detail page,
   * so МОП / МОЛ / МОТ can see at a glance from which locations the goods
   * will be picked up without drilling into each item. Sourced from
   * `quote_items.pickup_location_id` (FK → `kvota.locations`), deduplicated
   * by location id, sorted country → city to match the rest of the location
   * pickers.
   */
  pickupLocations: LocationOption[];
}

/**
 * Server-side fetcher for all data displayed in the quote detail context panel.
 * Replaces the previous client-side fetch in ContextPanel so the panel can be
 * a pure presentational component and the sales manager's email can be
 * resolved via the admin auth API (not reachable from the browser client).
 */
export async function fetchQuoteContextData(
  quoteId: string
): Promise<QuoteContextData> {
  const supabase = await createClient();

  // 1. Base quote fields needed for child lookups
  const { data: quoteRow } = await supabase
    .from("quotes")
    .select("sales_checklist, created_by, contact_person_id")
    .eq("id", quoteId)
    .is("deleted_at", null)
    .single();

  if (!quoteRow) {
    return {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
      procurementAssignees: [],
      logisticsAssignees: [],
      customsAssignees: [],
      pickupLocations: [],
    };
  }

  const salesChecklist =
    (quoteRow.sales_checklist as SalesChecklist | null) ?? null;
  const contactPersonId = quoteRow.contact_person_id ?? null;
  const createdBy = quoteRow.created_by ?? null;

  // 2. Parallel: contact person, sales manager profile, workflow transitions,
  //    invoice-level МОЛ/МОТ assignments, item-level МОЗ assignment +
  //    status_history rows that record the brand-slice routing moment (used
  //    as the canonical МОЗ "когда привязали" timestamp — Testing 2 row 79).
  const [
    contactRes,
    managerRes,
    transitionsRes,
    invoicesRes,
    itemsRes,
    statusHistoryRes,
  ] = await Promise.all([
    contactPersonId
      ? supabase
          .from("customer_contacts")
          .select("name, last_name, patronymic, phone, email")
          .eq("id", contactPersonId)
          .maybeSingle()
      : Promise.resolve({ data: null }),
    createdBy
      ? supabase
          .from("user_profiles")
          .select("user_id, full_name, phone")
          .eq("user_id", createdBy)
          .maybeSingle()
      : Promise.resolve({ data: null }),
    supabase
      .from("workflow_transitions")
      .select("id, from_status, to_status, actor_id, actor_role, created_at")
      .eq("quote_id", quoteId)
      .order("created_at", { ascending: true }),
    supabase
      .from("invoices")
      .select(
        "assigned_logistics_user, logistics_assigned_at, assigned_customs_user, customs_assigned_at"
      )
      .eq("quote_id", quoteId),
    supabase
      .from("quote_items")
      .select("assigned_procurement_user, brand, pickup_location_id")
      .eq("quote_id", quoteId),
    // status_history rows with reason='auto: all items routed' are inserted
    // by `maybeAdvanceBrandSlices` the moment every item of a (quote, brand)
    // slice has an `assigned_procurement_user` set — i.e. the exact moment a
    // МОЗ was attached to that brand. Joining via brand lets us surface the
    // real assignment timestamp even when the МОЗ hasn't yet acted on the
    // workflow themselves (Testing 2 row 79 / FB-260522).
    supabase
      .from("status_history")
      .select("brand, transitioned_at")
      .eq("quote_id", quoteId)
      .eq("reason", "auto: all items routed"),
  ]);

  const contactPerson: ContextPanelContact | null = contactRes.data
    ? {
        name: contactRes.data.name,
        last_name: contactRes.data.last_name ?? null,
        patronymic: contactRes.data.patronymic ?? null,
        phone: contactRes.data.phone ?? null,
        email: contactRes.data.email ?? null,
      }
    : null;

  // 3. Sales manager email via admin auth API (auth.users is not exposed
  //    through PostgREST). Only call if we have a manager profile.
  let salesManager: ContextPanelSalesManager | null = null;
  if (managerRes.data) {
    let email: string | null = null;
    try {
      const admin = createAdminClient();
      const { data: authUser } = await admin.auth.admin.getUserById(
        managerRes.data.user_id
      );
      email = authUser?.user?.email ?? null;
    } catch {
      email = null;
    }
    salesManager = {
      id: managerRes.data.user_id,
      full_name: managerRes.data.full_name ?? "",
      phone: managerRes.data.phone ?? null,
      email,
    };
  }

  // 4. Aggregate distinct МОЛ / МОТ assignees from per-invoice columns. A
  //    single user may cover multiple invoices on a quote — we keep the
  //    earliest timestamp so the panel mirrors the original "когда привязали"
  //    moment requested by РОЛ Тест 07 (3.1 / 4.1).
  const invoices = invoicesRes.data ?? [];
  const logisticsAt = new Map<string, string | null>();
  const customsAt = new Map<string, string | null>();
  for (const inv of invoices) {
    const lUser = inv.assigned_logistics_user ?? null;
    const lAt = inv.logistics_assigned_at ?? null;
    if (lUser) {
      const prev = logisticsAt.get(lUser);
      if (prev === undefined || (lAt && (!prev || lAt < prev))) {
        logisticsAt.set(lUser, lAt);
      }
    }
    const cUser = inv.assigned_customs_user ?? null;
    const cAt = inv.customs_assigned_at ?? null;
    if (cUser) {
      const prev = customsAt.get(cUser);
      if (prev === undefined || (cAt && (!prev || cAt < prev))) {
        customsAt.set(cUser, cAt);
      }
    }
  }

  // 4b. Aggregate distinct МОЗ assignees from per-item column. There is no
  //     dedicated assignment timestamp on `quote_items`, so we derive it
  //     from the brand-slice routing moment captured in `status_history`
  //     (reason = 'auto: all items routed'). When the slice has been
  //     auto-advanced we get the exact "когда привязали"; otherwise we
  //     leave the entry null and fall back to workflow_transitions below
  //     (legacy approximation for the user's own first transition).
  //
  //     Testing 2 row 79 (FB-260522): the old workflow_transitions-only
  //     back-fill returned null for МОЗ users who had been freshly
  //     attached but had not yet driven the workflow forward themselves,
  //     so the panel rendered ФИО without a date for every freshly
  //     distributed quote (РОЗ/СтМОЗ/МОЗ all complained).
  const items = itemsRes.data ?? [];
  const procurementAt = new Map<string, string | null>();
  // user_id → distinct brands assigned to that user on this quote.
  // Empty string for items without a brand — matches status_history.brand
  // convention used by the kanban auto-advance helper.
  const procurementUserBrands = new Map<string, Set<string>>();
  for (const it of items) {
    const pUser = it.assigned_procurement_user ?? null;
    if (!pUser) continue;
    if (!procurementAt.has(pUser)) procurementAt.set(pUser, null);
    const brandKey = it.brand ?? "";
    let brands = procurementUserBrands.get(pUser);
    if (!brands) {
      brands = new Set<string>();
      procurementUserBrands.set(pUser, brands);
    }
    brands.add(brandKey);
  }

  // brand → earliest "auto: all items routed" timestamp. Multiple slices
  // of the same brand can exist if a quote was re-distributed; we keep
  // the earliest to mirror the МОЛ/МОТ "first attach wins" semantic.
  const brandRoutedAt = new Map<string, string>();
  const statusHistoryRows = (statusHistoryRes.data ?? []) as Array<{
    brand: string | null;
    transitioned_at: string;
  }>;
  for (const row of statusHistoryRows) {
    if (!row.transitioned_at) continue;
    const brandKey = row.brand ?? "";
    const prev = brandRoutedAt.get(brandKey);
    if (!prev || row.transitioned_at < prev) {
      brandRoutedAt.set(brandKey, row.transitioned_at);
    }
  }

  // Fill МОЗ assigned_at from the earliest brand-routed timestamp across
  // all brands that user covers on this quote.
  for (const [userId, brands] of procurementUserBrands) {
    let earliest: string | null = null;
    for (const brand of brands) {
      const at = brandRoutedAt.get(brand);
      if (!at) continue;
      if (!earliest || at < earliest) earliest = at;
    }
    if (earliest) procurementAt.set(userId, earliest);
  }

  // 5. Batch-resolve all user names in one round-trip: transition actors +
  //    МОП (already loaded above) + МОЗ + МОЛ + МОТ.
  const transitions = transitionsRes.data ?? [];
  const allUserIds = new Set<string>(
    transitions.map((t) => t.actor_id).filter(Boolean) as string[]
  );
  for (const id of procurementAt.keys()) allUserIds.add(id);
  for (const id of logisticsAt.keys()) allUserIds.add(id);
  for (const id of customsAt.keys()) allUserIds.add(id);

  // Tertiary fallback: if `status_history` had no "auto: all items routed"
  // row for any of this user's brands (e.g. legacy quote that pre-dates the
  // kanban-auto-advance migration, or a brand-slice that was partially
  // routed and never crossed the gate), use the earliest workflow_transitions
  // row of the МОЗ themselves as a last-resort approximation. Skip when
  // status_history already supplied a timestamp.
  for (const t of transitions) {
    const uid = t.actor_id ?? null;
    if (!uid || !t.created_at) continue;
    if (!procurementAt.has(uid)) continue;
    const prev = procurementAt.get(uid);
    if (prev === null || (prev && t.created_at < prev)) {
      procurementAt.set(uid, t.created_at);
    }
  }

  const profileMap = new Map<string, string>();
  if (allUserIds.size > 0) {
    const { data: profiles } = await supabase
      .from("user_profiles")
      .select("user_id, full_name")
      .in("user_id", [...allUserIds]);
    for (const p of profiles ?? []) {
      profileMap.set(p.user_id, p.full_name ?? "Неизвестный");
    }
  }

  const participants: ContextPanelParticipant[] = transitions.map((t) => ({
    id: t.id,
    actor_id: t.actor_id ?? "",
    actor_role: t.actor_role ?? "",
    actor_name: profileMap.get(t.actor_id ?? "") ?? "Неизвестный",
    from_status: t.from_status ?? "",
    to_status: t.to_status ?? "",
    created_at: t.created_at,
  }));

  // 6. Resolve distinct pickup locations referenced by this quote's items.
  //    Two-step fetch (items → locations by id batch) instead of a PostgREST
  //    embed so we don't depend on FK auto-detection — kvota.quote_items has
  //    several FKs to `locations`-shaped tables historically and the customs
  //    refactor (Phase 5d) reshapes the embed surface again. A separate
  //    `.in("id", [...])` round-trip is one extra request but is robust to
  //    schema drift and matches the existing user_profiles batch pattern
  //    above. The data is small (one quote rarely has more than a handful
  //    of distinct pickup locations).
  const distinctLocationIds = new Set<string>();
  for (const it of items) {
    const lid = it.pickup_location_id ?? null;
    if (lid) distinctLocationIds.add(lid);
  }
  const pickupLocations: LocationOption[] = [];
  if (distinctLocationIds.size > 0) {
    const { data: locationRows } = await supabase
      .from("locations")
      .select("id, country, city, location_type")
      .in("id", [...distinctLocationIds]);
    const rows = (locationRows ?? []) as Array<{
      id: string;
      country: string;
      city: string | null;
      location_type: string | null;
    }>;
    pickupLocations.push(
      ...rows.map((r) => ({
        id: r.id,
        country: r.country,
        city: r.city ?? undefined,
        type: normaliseLocationType(r.location_type),
      })),
    );
    // Sort country → city (matches `fetchLocations` ordering so the info
    // panel and the route-constructor pickers list locations in the same
    // sequence — testers reading both surfaces in the same session don't
    // have to mentally re-sort).
    pickupLocations.sort((a, b) => {
      const c = a.country.localeCompare(b.country);
      if (c !== 0) return c;
      return (a.city ?? "").localeCompare(b.city ?? "");
    });
  }

  const buildAssignees = (
    src: Map<string, string | null>
  ): ContextPanelDomainAssignee[] =>
    [...src.entries()]
      .map(([user_id, assigned_at]) => ({
        user_id,
        full_name: profileMap.get(user_id) ?? "Неизвестный",
        assigned_at,
      }))
      // Stable sort: earliest assignment first, null timestamps last.
      .sort((a, b) => {
        if (a.assigned_at && b.assigned_at) {
          return a.assigned_at < b.assigned_at ? -1 : a.assigned_at > b.assigned_at ? 1 : 0;
        }
        if (a.assigned_at) return -1;
        if (b.assigned_at) return 1;
        return a.full_name.localeCompare(b.full_name);
      });

  return {
    salesChecklist,
    contactPerson,
    salesManager,
    participants,
    procurementAssignees: buildAssignees(procurementAt),
    logisticsAssignees: buildAssignees(logisticsAt),
    customsAssignees: buildAssignees(customsAt),
    pickupLocations,
  };
}
