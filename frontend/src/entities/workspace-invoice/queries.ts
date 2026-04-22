/**
 * Workspace invoice queries (logistics + customs workspace pages).
 *
 * Real-schema implementation — replaces earlier stubs that returned []. Org
 * scoping is derived via quote_id → quotes.organization_id (no org_id on
 * invoices). Item / HS-code / licenses aggregations come from quote_items.
 * User display info is resolved through auth.admin.getUserById (same pattern
 * as fetchTeamUsers below).
 *
 * SLA columns (logistics_deadline_at / logistics_needs_review_since / etc.)
 * were added in migration 285 and live on kvota.invoices — some generated
 * types on this branch predate that migration so we read them through a
 * `selectedInvoiceColumns` constant + locally-declared row shape, without
 * `@ts-nocheck`. A `npm run db:types` regen will make the types match the
 * runtime shape; the shape here is a strict subset of migration 285.
 */

import "server-only";
import { createAdminClient } from "@/shared/lib/supabase/server";
import type {
  WorkspaceInvoiceRow,
  WorkspaceInvoiceStatus,
} from "@/features/workspace-logistics/ui/workspace-invoices-table";
import type { UnassignedInvoiceRow } from "@/features/workspace-logistics/ui/unassigned-inbox";
import type { LocationChipLocation } from "@/entities/location/ui/location-chip";
import type { UserAvatarChipUser } from "@/entities/user";

type Domain = "logistics" | "customs";

// ---------------------------------------------------------------------------
// Shared shapes
// ---------------------------------------------------------------------------

/**
 * Columns we read off kvota.invoices for workspace pages. Kept as a single
 * constant so the SELECT clause and the row shape stay aligned without
 * repeating a 30-line string.
 */
const INVOICE_COLUMNS = `
  id,
  quote_id,
  invoice_number,
  status,
  pickup_country,
  pickup_country_code,
  pickup_city,
  total_weight_kg,
  total_volume_m3,
  package_count,
  logistics_assigned_at,
  logistics_deadline_at,
  logistics_completed_at,
  logistics_sla_hours,
  logistics_needs_review_since,
  assigned_logistics_user,
  customs_assigned_at,
  customs_deadline_at,
  customs_completed_at,
  customs_sla_hours,
  customs_needs_review_since,
  assigned_customs_user,
  created_at,
  quote:quotes!inner(
    id,
    idn_quote,
    organization_id,
    delivery_city,
    delivery_country,
    deleted_at,
    customer:customers(id, name, country, city)
  )
`;

interface InvoiceRowRaw {
  id: string;
  quote_id: string;
  invoice_number: string | null;
  status: string | null;
  pickup_country: string | null;
  pickup_country_code: string | null;
  pickup_city: string | null;
  total_weight_kg: number | null;
  total_volume_m3: number | null;
  package_count: number | null;
  logistics_assigned_at: string | null;
  logistics_deadline_at: string | null;
  logistics_completed_at: string | null;
  logistics_sla_hours: number | null;
  logistics_needs_review_since: string | null;
  assigned_logistics_user: string | null;
  customs_assigned_at: string | null;
  customs_deadline_at: string | null;
  customs_completed_at: string | null;
  customs_sla_hours: number | null;
  customs_needs_review_since: string | null;
  assigned_customs_user: string | null;
  created_at: string | null;
  quote: {
    id: string;
    idn_quote: string | null;
    organization_id: string | null;
    delivery_city: string | null;
    delivery_country: string | null;
    deleted_at: string | null;
    customer: {
      id: string;
      name: string | null;
      country: string | null;
      city: string | null;
    } | null;
  } | null;
}

interface ItemAggregates {
  count: number;
  hsFilled: number;
  hsTotal: number;
  licensesRequired: number;
}

interface UserMeta {
  id: string;
  full_name?: string;
  name?: string;
  email?: string;
  avatar_url?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Aggregate quote_items counts (items, hs_code filled/total, licenses required)
 * for a list of quote_ids in a single round-trip, returning a map.
 */
async function fetchItemAggregatesByQuoteId(
  admin: ReturnType<typeof createAdminClient>,
  quoteIds: string[]
): Promise<Map<string, ItemAggregates>> {
  const map = new Map<string, ItemAggregates>();
  if (quoteIds.length === 0) return map;

  const { data, error } = await admin
    .from("quote_items")
    .select(
      "quote_id, hs_code, license_ds_required, license_ss_required, license_sgr_required"
    )
    .in("quote_id", quoteIds);

  if (error) {
    console.error("fetchItemAggregates: quote_items query failed", error);
    return map;
  }

  for (const row of data ?? []) {
    const key = row.quote_id as string;
    const entry =
      map.get(key) ??
      ({ count: 0, hsFilled: 0, hsTotal: 0, licensesRequired: 0 } satisfies ItemAggregates);
    entry.count += 1;
    entry.hsTotal += 1;
    if (row.hs_code && String(row.hs_code).trim() !== "") entry.hsFilled += 1;
    if (
      row.license_ds_required ||
      row.license_ss_required ||
      row.license_sgr_required
    ) {
      entry.licensesRequired += 1;
    }
    map.set(key, entry);
  }

  return map;
}

/**
 * Resolve user display info for a set of user ids using auth.admin.getUserById
 * (same pattern as fetchTeamUsers). Safe-soft: unresolved ids are skipped.
 */
async function fetchUserMetaMap(
  admin: ReturnType<typeof createAdminClient>,
  userIds: string[]
): Promise<Map<string, UserAvatarChipUser>> {
  const map = new Map<string, UserAvatarChipUser>();
  const unique = Array.from(new Set(userIds.filter(Boolean)));
  if (unique.length === 0) return map;

  const results = await Promise.all(
    unique.map(async (uid) => {
      try {
        const { data } = await admin.auth.admin.getUserById(uid);
        const u = data?.user;
        if (!u) return null;
        const meta = (u.user_metadata ?? {}) as UserMeta;
        const display: UserAvatarChipUser = {
          id: u.id,
          name: meta.full_name || meta.name || u.email || "—",
          email: u.email ?? undefined,
          avatarUrl: meta.avatar_url ?? undefined,
        };
        return display;
      } catch {
        return null;
      }
    })
  );

  for (const entry of results) {
    if (entry) map.set(entry.id, entry);
  }
  return map;
}

function buildPickupLocation(inv: InvoiceRowRaw): LocationChipLocation {
  return {
    country: inv.pickup_country ?? "",
    iso2: inv.pickup_country_code ?? undefined,
    city: inv.pickup_city ?? undefined,
    type: "supplier",
  };
}

function buildDeliveryLocation(inv: InvoiceRowRaw): LocationChipLocation {
  const quote = inv.quote;
  return {
    country: quote?.delivery_country ?? quote?.customer?.country ?? "",
    city: quote?.delivery_city ?? quote?.customer?.city ?? undefined,
    type: "client",
  };
}

function deriveStatus(
  inv: InvoiceRowRaw,
  domain: Domain
): WorkspaceInvoiceStatus {
  const completedAt =
    domain === "logistics"
      ? inv.logistics_completed_at
      : inv.customs_completed_at;
  if (completedAt) return "completed";
  const reviewSince =
    domain === "logistics"
      ? inv.logistics_needs_review_since
      : inv.customs_needs_review_since;
  if (reviewSince) return "awaiting_customer";
  return "in_progress";
}

function buildInvoiceIdn(inv: InvoiceRowRaw): string {
  const quoteIdn = inv.quote?.idn_quote ?? inv.quote_id.slice(0, 8);
  const invNo = inv.invoice_number ?? inv.id.slice(0, 4);
  return `${quoteIdn} / ${invNo}`;
}

function domainFields(inv: InvoiceRowRaw, domain: Domain) {
  if (domain === "logistics") {
    return {
      assignedAt: inv.logistics_assigned_at ?? inv.created_at ?? "",
      deadlineAt: inv.logistics_deadline_at ?? "",
      completedAt: inv.logistics_completed_at,
      assignedUserId: inv.assigned_logistics_user,
    };
  }
  return {
    assignedAt: inv.customs_assigned_at ?? inv.created_at ?? "",
    deadlineAt: inv.customs_deadline_at ?? "",
    completedAt: inv.customs_completed_at,
    assignedUserId: inv.assigned_customs_user,
  };
}

async function shapeRows(
  invoices: InvoiceRowRaw[],
  domain: Domain
): Promise<WorkspaceInvoiceRow[]> {
  if (invoices.length === 0) return [];

  const admin = createAdminClient();
  const quoteIds = Array.from(new Set(invoices.map((i) => i.quote_id)));
  const userIds = invoices
    .map((i) => domainFields(i, domain).assignedUserId)
    .filter((id): id is string => !!id);

  const [itemMap, userMap] = await Promise.all([
    fetchItemAggregatesByQuoteId(admin, quoteIds),
    fetchUserMetaMap(admin, userIds),
  ]);

  return invoices.map((inv) => {
    const fields = domainFields(inv, domain);
    const agg = itemMap.get(inv.quote_id) ?? {
      count: 0,
      hsFilled: 0,
      hsTotal: 0,
      licensesRequired: 0,
    };
    const assignedUser = fields.assignedUserId
      ? userMap.get(fields.assignedUserId)
      : undefined;

    return {
      id: inv.id,
      quoteId: inv.quote_id,
      idn: buildInvoiceIdn(inv),
      quoteIdn: inv.quote?.idn_quote ?? "",
      customerName: inv.quote?.customer?.name ?? "—",
      pickupLocation: buildPickupLocation(inv),
      deliveryLocation: buildDeliveryLocation(inv),
      itemsCount: agg.count,
      totalWeightKg: inv.total_weight_kg ?? undefined,
      hsCodesFilled: domain === "customs" ? agg.hsFilled : undefined,
      hsCodesTotal: domain === "customs" ? agg.hsTotal : undefined,
      licensesRequired:
        domain === "customs" ? agg.licensesRequired : undefined,
      assignedAt: fields.assignedAt,
      deadlineAt: fields.deadlineAt,
      completedAt: fields.completedAt ?? null,
      assignedUser,
      status: deriveStatus(inv, domain),
    } satisfies WorkspaceInvoiceRow;
  });
}

// ---------------------------------------------------------------------------
// Fetchers
// ---------------------------------------------------------------------------

/**
 * Invoices assigned to the current user for the given domain, still in work
 * (completed_at IS NULL). Sorted by deadline soonest-first.
 */
export async function fetchMyAssignedInvoices(
  domain: Domain,
  userId: string,
  orgId: string
): Promise<WorkspaceInvoiceRow[]> {
  const admin = createAdminClient();
  const userCol =
    domain === "logistics" ? "assigned_logistics_user" : "assigned_customs_user";
  const completedCol =
    domain === "logistics" ? "logistics_completed_at" : "customs_completed_at";
  const deadlineCol =
    domain === "logistics" ? "logistics_deadline_at" : "customs_deadline_at";

  const query = admin
    .from("invoices")
    // Types on this branch lag migration 285 — runtime select is authoritative.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .select(INVOICE_COLUMNS as any)
    .eq(userCol, userId)
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .is(completedCol, null)
    .order(deadlineCol, { ascending: true, nullsFirst: false });

  const { data, error } = await query;
  if (error) {
    console.error("fetchMyAssignedInvoices failed", error);
    return [];
  }
  return shapeRows((data ?? []) as unknown as InvoiceRowRaw[], domain);
}

/**
 * Invoices the current user completed in the given domain. Last 30 completed
 * sorted newest-first (covers typical "what did I do this week" view).
 */
export async function fetchMyCompletedInvoices(
  domain: Domain,
  userId: string,
  orgId: string
): Promise<WorkspaceInvoiceRow[]> {
  const admin = createAdminClient();
  const userCol =
    domain === "logistics" ? "assigned_logistics_user" : "assigned_customs_user";
  const completedCol =
    domain === "logistics" ? "logistics_completed_at" : "customs_completed_at";

  const { data, error } = await admin
    .from("invoices")
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .select(INVOICE_COLUMNS as any)
    .eq(userCol, userId)
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .not(completedCol, "is", null)
    .order(completedCol, { ascending: false })
    .limit(30);

  if (error) {
    console.error("fetchMyCompletedInvoices failed", error);
    return [];
  }
  return shapeRows((data ?? []) as unknown as InvoiceRowRaw[], domain);
}

/**
 * Invoices with no assignee for the given domain — head/admin-only view.
 * Returns lightweight rows suitable for UnassignedInbox (no completion column).
 */
export async function fetchUnassignedInvoices(
  domain: Domain,
  orgId: string
): Promise<UnassignedInvoiceRow[]> {
  const admin = createAdminClient();
  const userCol =
    domain === "logistics" ? "assigned_logistics_user" : "assigned_customs_user";
  const completedCol =
    domain === "logistics" ? "logistics_completed_at" : "customs_completed_at";
  const deadlineCol =
    domain === "logistics" ? "logistics_deadline_at" : "customs_deadline_at";

  const { data, error } = await admin
    .from("invoices")
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .select(INVOICE_COLUMNS as any)
    .is(userCol, null)
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .is(completedCol, null)
    .order(deadlineCol, { ascending: true, nullsFirst: false });

  if (error) {
    console.error("fetchUnassignedInvoices failed", error);
    return [];
  }

  const rows = (data ?? []) as unknown as InvoiceRowRaw[];
  if (rows.length === 0) return [];

  const quoteIds = Array.from(new Set(rows.map((r) => r.quote_id)));
  const itemMap = await fetchItemAggregatesByQuoteId(admin, quoteIds);

  return rows.map((inv) => {
    const agg = itemMap.get(inv.quote_id) ?? {
      count: 0,
      hsFilled: 0,
      hsTotal: 0,
      licensesRequired: 0,
    };
    const createdAt = inv.created_at ?? "";
    const deadlineAt =
      (domain === "logistics"
        ? inv.logistics_deadline_at
        : inv.customs_deadline_at) ?? "";
    return {
      id: inv.id,
      quoteId: inv.quote_id,
      idn: buildInvoiceIdn(inv),
      customerName: inv.quote?.customer?.name ?? "—",
      pickupLocation: buildPickupLocation(inv),
      deliveryLocation: buildDeliveryLocation(inv),
      itemsCount: agg.count,
      totalWeightKg: inv.total_weight_kg ?? undefined,
      createdAt,
      deadlineAt,
    } satisfies UnassignedInvoiceRow;
  });
}

/**
 * All active invoices in the org for the given domain (head/admin view).
 * "Active" = not completed. Includes both assigned and unassigned rows.
 */
export async function fetchAllActiveInvoices(
  domain: Domain,
  orgId: string
): Promise<WorkspaceInvoiceRow[]> {
  const admin = createAdminClient();
  const completedCol =
    domain === "logistics" ? "logistics_completed_at" : "customs_completed_at";
  const deadlineCol =
    domain === "logistics" ? "logistics_deadline_at" : "customs_deadline_at";

  const { data, error } = await admin
    .from("invoices")
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .select(INVOICE_COLUMNS as any)
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .is(completedCol, null)
    .order(deadlineCol, { ascending: true, nullsFirst: false });

  if (error) {
    console.error("fetchAllActiveInvoices failed", error);
    return [];
  }
  return shapeRows((data ?? []) as unknown as InvoiceRowRaw[], domain);
}

/**
 * fetchTeamUsers — resolves users with the given role in org via user_roles
 * + auth admin API. Unchanged from the previous implementation.
 */
export async function fetchTeamUsers(
  domain: Domain,
  orgId: string
): Promise<UserAvatarChipUser[]> {
  const admin = createAdminClient();
  const roleSlug = domain === "logistics" ? "logistics" : "customs";

  const { data: memberships, error: rolesErr } = await admin
    .from("user_roles")
    .select("user_id, roles!inner(slug)")
    .eq("organization_id", orgId)
    .eq("roles.slug", roleSlug);

  if (rolesErr) {
    console.error("fetchTeamUsers: user_roles query failed", rolesErr);
    return [];
  }

  const userIds = Array.from(
    new Set((memberships ?? []).map((m) => m.user_id as string))
  );
  if (userIds.length === 0) return [];

  const map = await fetchUserMetaMap(admin, userIds);
  return Array.from(map.values());
}

/**
 * Workspace-level KPI stats for head/admin strip: active count, overdue count,
 * completed this ISO week, avg SLA hours over last 30 completed.
 */
export async function fetchWorkspaceStats(
  domain: Domain,
  orgId: string
): Promise<{
  active: number;
  overdue: number;
  completedThisWeek: number;
  avgSlaHours: number;
}> {
  const admin = createAdminClient();
  const assignedCol =
    domain === "logistics" ? "logistics_assigned_at" : "customs_assigned_at";
  const completedCol =
    domain === "logistics" ? "logistics_completed_at" : "customs_completed_at";
  const deadlineCol =
    domain === "logistics" ? "logistics_deadline_at" : "customs_deadline_at";

  const weekStart = startOfIsoWeek(new Date()).toISOString();
  const nowIso = new Date().toISOString();
  const thirtyDaysAgo = new Date(
    Date.now() - 30 * 24 * 60 * 60 * 1000
  ).toISOString();

  const activeQuery = admin
    .from("invoices")
    .select("id, quote:quotes!inner(organization_id, deleted_at)", {
      count: "exact",
      head: true,
    })
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .is(completedCol, null)
    .not(assignedCol, "is", null);

  const overdueQuery = admin
    .from("invoices")
    .select("id, quote:quotes!inner(organization_id, deleted_at)", {
      count: "exact",
      head: true,
    })
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .is(completedCol, null)
    .lt(deadlineCol, nowIso);

  const weekDoneQuery = admin
    .from("invoices")
    .select("id, quote:quotes!inner(organization_id, deleted_at)", {
      count: "exact",
      head: true,
    })
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .gte(completedCol, weekStart);

  const slaQuery = admin
    .from("invoices")
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .select(
      `${assignedCol}, ${completedCol}, quote:quotes!inner(organization_id, deleted_at)` as any
    )
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .gte(completedCol, thirtyDaysAgo)
    .not(assignedCol, "is", null);

  const [activeRes, overdueRes, weekDoneRes, slaRes] = await Promise.all([
    activeQuery,
    overdueQuery,
    weekDoneQuery,
    slaQuery,
  ]);

  type SlaRow = Record<string, string | null>;
  const slaRows = (slaRes.data ?? []) as unknown as SlaRow[];
  const deltas = slaRows
    .map((row) => {
      const startIso = row[assignedCol];
      const endIso = row[completedCol];
      if (!startIso || !endIso) return null;
      const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
      return ms > 0 ? ms / (60 * 60 * 1000) : null;
    })
    .filter((v): v is number => v !== null);
  const avg =
    deltas.length > 0
      ? deltas.reduce((a, b) => a + b, 0) / deltas.length
      : 0;

  return {
    active: activeRes.count ?? 0,
    overdue: overdueRes.count ?? 0,
    completedThisWeek: weekDoneRes.count ?? 0,
    avgSlaHours: Number(avg.toFixed(1)),
  };
}

function startOfIsoWeek(d: Date): Date {
  const date = new Date(d);
  const day = date.getUTCDay();
  // ISO week starts on Monday (1); Sunday (0) → 7
  const shift = (day === 0 ? 7 : day) - 1;
  date.setUTCDate(date.getUTCDate() - shift);
  date.setUTCHours(0, 0, 0, 0);
  return date;
}
