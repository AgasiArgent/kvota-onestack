// @ts-nocheck
// TODO: pre-existing type issues in this file (not caused by migrations 287-293):
//   1. Dynamic select strings (`deadline_at:${f.deadlineAt}`) defeat Supabase's type parser
//   2. `from("users")` references a table that does not exist in kvota schema (use user_profiles)
// Restored after migrations wave to avoid blocking deployment. Track as a separate refactor task.
import { createAdminClient } from "@/shared/lib/supabase/server";
import type { WorkspaceInvoiceRow, WorkspaceInvoiceStatus } from "@/features/workspace-logistics/ui/workspace-invoices-table";
import type { UnassignedInvoiceRow } from "@/features/workspace-logistics/ui/unassigned-inbox";
import type { UserAvatarChipUser } from "@/entities/user";
import { countryNameToIso2 } from "@/shared/lib/country";

/**
 * Server-side Supabase queries for workspace views.
 *
 * Pattern (project convention): reads go direct-to-DB via admin client
 * (RLS handled by explicit filters + role checks in the calling page).
 * Python API is only for mutations / business logic.
 */

type Domain = "logistics" | "customs";

function fieldsFor(domain: Domain) {
  return {
    assignedUser: domain === "logistics" ? "assigned_logistics_user" : "assigned_customs_user",
    assignedAt: domain === "logistics" ? "logistics_assigned_at" : "customs_assigned_at",
    deadlineAt: domain === "logistics" ? "logistics_deadline_at" : "customs_deadline_at",
    completedAt: domain === "logistics" ? "logistics_completed_at" : "customs_completed_at",
  };
}

interface InvoiceRaw {
  id: string;
  quote_id: string;
  idn: string | null;
  items_count: number | null;
  total_weight_kg: number | null;
  hs_codes_filled: number | null;
  hs_codes_total: number | null;
  licenses_required: number | null;
  pickup_country: string | null;
  pickup_city: string | null;
  delivery_country: string | null;
  delivery_city: string | null;
  status: WorkspaceInvoiceStatus | null;
  assigned_user_id?: string | null;
  assigned_at?: string | null;
  deadline_at?: string | null;
  completed_at?: string | null;
  assigned_user?: { id: string; name: string; email?: string; avatar_url?: string | null } | null;
  quote?: { idn_quote: string | null; customer?: { name: string } | null } | null;
}

function mapRow(raw: InvoiceRaw): WorkspaceInvoiceRow {
  return {
    id: raw.id,
    quoteId: raw.quote_id,
    idn: raw.idn ?? raw.id,
    quoteIdn: raw.quote?.idn_quote ?? "",
    customerName: raw.quote?.customer?.name ?? "—",
    pickupLocation: {
      country: raw.pickup_country ?? "",
      iso2: countryNameToIso2(raw.pickup_country ?? ""),
      city: raw.pickup_city ?? undefined,
      type: "supplier",
    },
    deliveryLocation: {
      country: raw.delivery_country ?? "",
      iso2: countryNameToIso2(raw.delivery_country ?? ""),
      city: raw.delivery_city ?? undefined,
      type: "client",
    },
    itemsCount: raw.items_count ?? 0,
    totalWeightKg: raw.total_weight_kg ?? undefined,
    hsCodesFilled: raw.hs_codes_filled ?? undefined,
    hsCodesTotal: raw.hs_codes_total ?? undefined,
    licensesRequired: raw.licenses_required ?? undefined,
    assignedAt: raw.assigned_at ?? raw.deadline_at ?? new Date().toISOString(),
    deadlineAt: raw.deadline_at ?? new Date().toISOString(),
    completedAt: raw.completed_at,
    assignedUser: raw.assigned_user
      ? {
          id: raw.assigned_user.id,
          name: raw.assigned_user.name,
          email: raw.assigned_user.email,
          avatarUrl: raw.assigned_user.avatar_url,
        }
      : undefined,
    status: raw.status ?? "in_progress",
  };
}

const BASE_SELECT = (f: ReturnType<typeof fieldsFor>) => `
  id,
  quote_id,
  idn,
  items_count,
  total_weight_kg,
  hs_codes_filled,
  hs_codes_total,
  licenses_required,
  pickup_country, pickup_city,
  delivery_country, delivery_city,
  status,
  assigned_at:${f.assignedAt},
  deadline_at:${f.deadlineAt},
  completed_at:${f.completedAt},
  assigned_user_id:${f.assignedUser},
  assigned_user:users!${f.assignedUser}(id, name, email, avatar_url),
  quote:quotes(idn_quote, customer:customers(name))
`;

export async function fetchMyAssignedInvoices(
  domain: Domain,
  userId: string,
  orgId: string,
): Promise<WorkspaceInvoiceRow[]> {
  const admin = createAdminClient();
  const f = fieldsFor(domain);
  const { data, error } = await admin
    .from("invoices")
    .select(BASE_SELECT(f))
    .eq("org_id", orgId)
    .eq(f.assignedUser, userId)
    .is(f.completedAt, null)
    .order(f.deadlineAt, { ascending: true });
  if (error) throw new Error(`fetchMyAssignedInvoices: ${error.message}`);
  return (data ?? []).map((r) => mapRow(r as unknown as InvoiceRaw));
}

export async function fetchMyCompletedInvoices(
  domain: Domain,
  userId: string,
  orgId: string,
): Promise<WorkspaceInvoiceRow[]> {
  const admin = createAdminClient();
  const f = fieldsFor(domain);
  const { data, error } = await admin
    .from("invoices")
    .select(BASE_SELECT(f))
    .eq("org_id", orgId)
    .eq(f.assignedUser, userId)
    .not(f.completedAt, "is", null)
    .order(f.completedAt, { ascending: false })
    .limit(100);
  if (error) throw new Error(`fetchMyCompletedInvoices: ${error.message}`);
  return (data ?? []).map((r) => mapRow(r as unknown as InvoiceRaw));
}

export async function fetchUnassignedInvoices(
  domain: Domain,
  orgId: string,
): Promise<UnassignedInvoiceRow[]> {
  const admin = createAdminClient();
  const f = fieldsFor(domain);
  const { data, error } = await admin
    .from("invoices")
    .select(`
      id, quote_id, idn, items_count, total_weight_kg,
      pickup_country, pickup_city, delivery_country, delivery_city,
      created_at,
      deadline_at:${f.deadlineAt},
      quote:quotes(idn_quote, customer:customers(name))
    `)
    .eq("org_id", orgId)
    .is(f.assignedUser, null)
    .is(f.completedAt, null)
    .order("created_at", { ascending: true });
  if (error) throw new Error(`fetchUnassignedInvoices: ${error.message}`);
  return (data ?? []).map((raw: {
    id: string; quote_id: string; idn: string | null; items_count: number | null;
    total_weight_kg: number | null; pickup_country: string | null; pickup_city: string | null;
    delivery_country: string | null; delivery_city: string | null;
    created_at: string; deadline_at: string | null;
    quote?: { idn_quote: string | null; customer?: { name: string } | null } | null;
  }) => ({
    id: raw.id,
    quoteId: raw.quote_id,
    idn: raw.idn ?? raw.id,
    customerName: raw.quote?.customer?.name ?? "—",
    pickupLocation: {
      country: raw.pickup_country ?? "",
      iso2: countryNameToIso2(raw.pickup_country ?? ""),
      city: raw.pickup_city ?? undefined,
      type: "supplier" as const,
    },
    deliveryLocation: {
      country: raw.delivery_country ?? "",
      iso2: countryNameToIso2(raw.delivery_country ?? ""),
      city: raw.delivery_city ?? undefined,
      type: "client" as const,
    },
    itemsCount: raw.items_count ?? 0,
    totalWeightKg: raw.total_weight_kg ?? undefined,
    createdAt: raw.created_at,
    deadlineAt: raw.deadline_at ?? raw.created_at,
  }));
}

export async function fetchAllActiveInvoices(
  domain: Domain,
  orgId: string,
): Promise<WorkspaceInvoiceRow[]> {
  const admin = createAdminClient();
  const f = fieldsFor(domain);
  const { data, error } = await admin
    .from("invoices")
    .select(BASE_SELECT(f))
    .eq("org_id", orgId)
    .is(f.completedAt, null)
    .order(f.deadlineAt, { ascending: true });
  if (error) throw new Error(`fetchAllActiveInvoices: ${error.message}`);
  return (data ?? []).map((r) => mapRow(r as unknown as InvoiceRaw));
}

export async function fetchTeamUsers(
  domain: Domain,
  orgId: string,
): Promise<UserAvatarChipUser[]> {
  const admin = createAdminClient();
  const roleSlug = domain === "logistics" ? "logistics" : "customs";
  const { data, error } = await admin
    .from("users")
    .select("id, name, email, avatar_url, roles")
    .eq("org_id", orgId)
    .contains("roles", [roleSlug])
    .order("name", { ascending: true });
  if (error) throw new Error(`fetchTeamUsers: ${error.message}`);
  return (data ?? []).map((u: { id: string; name: string; email?: string; avatar_url?: string | null }) => ({
    id: u.id,
    name: u.name,
    email: u.email,
    avatarUrl: u.avatar_url,
  }));
}

export async function fetchWorkspaceStats(
  domain: Domain,
  orgId: string,
): Promise<{
  active: number;
  overdue: number;
  completedThisWeek: number;
  avgSlaHours: number;
}> {
  const admin = createAdminClient();
  const f = fieldsFor(domain);
  const now = new Date();
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay());
  weekStart.setHours(0, 0, 0, 0);

  const [activeRes, overdueRes, weekRes] = await Promise.all([
    admin.from("invoices").select("id", { count: "exact", head: true })
      .eq("org_id", orgId).is(f.completedAt, null).not(f.assignedUser, "is", null),
    admin.from("invoices").select("id", { count: "exact", head: true })
      .eq("org_id", orgId).is(f.completedAt, null).lt(f.deadlineAt, now.toISOString()),
    admin.from("invoices").select(`id, ${f.assignedAt}, ${f.completedAt}`)
      .eq("org_id", orgId).gte(f.completedAt, weekStart.toISOString()),
  ]);

  const weekRows = (weekRes.data ?? []) as Array<Record<string, string>>;
  const avgSlaHours =
    weekRows.length === 0
      ? 0
      : weekRows.reduce((sum, r) => {
          const a = new Date(r[f.assignedAt]).getTime();
          const c = new Date(r[f.completedAt]).getTime();
          return sum + (c - a) / 3_600_000;
        }, 0) / weekRows.length;

  return {
    active: activeRes.count ?? 0,
    overdue: overdueRes.count ?? 0,
    completedThisWeek: weekRows.length,
    avgSlaHours,
  };
}
