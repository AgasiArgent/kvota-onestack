/**
 * Workspace invoice queries (logistics + customs kanban boards).
 *
 * Org scoping is derived via quote_id → quotes.organization_id (no org_id on
 * invoices). Item counts come from quote_items. User display info is resolved
 * through auth.admin.getUserById (same pattern as fetchTeamUsers).
 *
 * SLA columns (logistics_deadline_at / customs_deadline_at / etc.) were added
 * in migration 285 and live on kvota.invoices — some generated types on this
 * branch predate that migration so we read them through an `INVOICE_COLUMNS`
 * constant + locally-declared row shape, without `@ts-nocheck`. A
 * `npm run db:types` regen will make the types match the runtime shape.
 */

import "server-only";
import { createAdminClient } from "@/shared/lib/supabase/server";
import type { LocationChipLocation } from "@/entities/location/ui/location-chip";
import type { UserAvatarChipUser } from "@/entities/user";
import type {
  WorkspaceDomain,
  WorkspaceKanbanBoard,
  WorkspaceKanbanCard,
  WorkspaceCargoPlace,
} from "./model/types";
import { deriveKanbanColumn, isCardVisibleToUser } from "./model/types";

// ---------------------------------------------------------------------------
// Shared shapes
// ---------------------------------------------------------------------------

/**
 * Columns we read off kvota.invoices for the kanban board. Kept as a single
 * constant so the SELECT clause and the row shape stay aligned.
 *
 * `procurement_completed_at` is the stage-entry timestamp (REQ-4 — the timer
 * starts on stage entry, independent of assignment). `cargo_places` is the
 * nested invoice_cargo_places join (REQ-10 cargo dimensions).
 */
const INVOICE_COLUMNS = `
  id,
  quote_id,
  invoice_number,
  pickup_country,
  pickup_country_code,
  pickup_city,
  total_weight_kg,
  total_volume_m3,
  package_count,
  procurement_completed_at,
  logistics_assigned_at,
  logistics_deadline_at,
  logistics_completed_at,
  assigned_logistics_user,
  customs_assigned_at,
  customs_deadline_at,
  customs_completed_at,
  assigned_customs_user,
  created_at,
  cargo_places:invoice_cargo_places(position, weight_kg, length_mm, width_mm, height_mm),
  quote:quotes!inner(
    id,
    idn_quote,
    organization_id,
    workflow_status,
    delivery_city,
    delivery_country,
    deleted_at,
    total_amount,
    currency,
    sales_checklist,
    customer:customers(id, name, country, city)
  )
`;

interface CargoPlaceRaw {
  position: number;
  weight_kg: number | null;
  length_mm: number | null;
  width_mm: number | null;
  height_mm: number | null;
}

/**
 * Minimal projection of `kvota.quotes.sales_checklist` (JSONB) — only the
 * `distribution_comment` is consumed on the kanban card surface. Other keys
 * (is_estimate / is_tender / equipment_description / …) are read on the
 * context panel via its own fetcher and don't need to be replicated here.
 */
interface SalesChecklistRaw {
  distribution_comment?: string | null;
}

interface InvoiceRowRaw {
  id: string;
  quote_id: string;
  invoice_number: string | null;
  pickup_country: string | null;
  pickup_country_code: string | null;
  pickup_city: string | null;
  total_weight_kg: number | null;
  total_volume_m3: number | null;
  package_count: number | null;
  procurement_completed_at: string | null;
  logistics_assigned_at: string | null;
  logistics_deadline_at: string | null;
  logistics_completed_at: string | null;
  assigned_logistics_user: string | null;
  customs_assigned_at: string | null;
  customs_deadline_at: string | null;
  customs_completed_at: string | null;
  assigned_customs_user: string | null;
  created_at: string | null;
  cargo_places: CargoPlaceRaw[] | null;
  quote: {
    id: string;
    idn_quote: string | null;
    organization_id: string | null;
    workflow_status: string | null;
    delivery_city: string | null;
    delivery_country: string | null;
    deleted_at: string | null;
    total_amount: number | null;
    currency: string | null;
    sales_checklist: SalesChecklistRaw | null;
    customer: {
      id: string;
      name: string | null;
      country: string | null;
      city: string | null;
    } | null;
  } | null;
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
 * Aggregate quote_items counts (number of items) for a list of quote_ids in a
 * single round-trip, returning a quote_id → count map.
 */
async function fetchItemCountsByQuoteId(
  admin: ReturnType<typeof createAdminClient>,
  quoteIds: string[]
): Promise<Map<string, number>> {
  const map = new Map<string, number>();
  if (quoteIds.length === 0) return map;

  const { data, error } = await admin
    .from("quote_items")
    .select("quote_id")
    .in("quote_id", quoteIds);

  if (error) {
    console.error("fetchItemCounts: quote_items query failed", error);
    return map;
  }

  for (const row of data ?? []) {
    const key = row.quote_id as string;
    map.set(key, (map.get(key) ?? 0) + 1);
  }
  return map;
}

/**
 * Resolve user display info for a set of user ids.
 *
 * The ФИО (full name) lives in `kvota.user_profiles.full_name` — the same
 * source the quotes-list МОЛ/МОЗ chips read. `auth.users.user_metadata` is
 * NOT a reliable name source (most accounts only have an email there), so the
 * kanban card would show an email instead of a name. We batch-fetch
 * user_profiles for the name and fall back to the auth email only when no
 * profile name exists. Safe-soft: unresolved ids are skipped.
 */
async function fetchUserMetaMap(
  admin: ReturnType<typeof createAdminClient>,
  userIds: string[]
): Promise<Map<string, UserAvatarChipUser>> {
  const map = new Map<string, UserAvatarChipUser>();
  const unique = Array.from(new Set(userIds.filter(Boolean)));
  if (unique.length === 0) return map;

  // ФИО from user_profiles (single round-trip).
  const { data: profiles, error: profilesErr } = await admin
    .from("user_profiles")
    .select("user_id, full_name")
    .in("user_id", unique);
  if (profilesErr) {
    console.error("fetchUserMetaMap: user_profiles query failed", profilesErr);
  }
  const nameById = new Map<string, string>();
  for (const p of profiles ?? []) {
    const name = (p.full_name ?? "").trim();
    if (name) nameById.set(p.user_id, name);
  }

  // Email fallback (and avatar) from auth — only used when no ФИО exists.
  const results = await Promise.all(
    unique.map(async (uid) => {
      try {
        const { data } = await admin.auth.admin.getUserById(uid);
        const u = data?.user;
        if (!u) return null;
        const meta = (u.user_metadata ?? {}) as UserMeta;
        const display: UserAvatarChipUser = {
          id: u.id,
          name:
            nameById.get(uid) ||
            meta.full_name ||
            meta.name ||
            // Last-ditch fallback: derive a short label from the email's
            // local part (e.g. "ekaterina.kravtsova@…" → "ekaterina.kravtsova")
            // so the chip never leaks the raw "name@domain" to assignee
            // surfaces. Testing 2 rows 40-41: tester saw full emails in
            // Исполнитель column for users whose user_profiles.full_name
            // was empty.
            (u.email ? u.email.split("@")[0] : "") ||
            "—",
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

function buildInvoiceIdn(inv: InvoiceRowRaw): string {
  const quoteIdn = inv.quote?.idn_quote ?? inv.quote_id.slice(0, 8);
  const invNo = inv.invoice_number ?? inv.id.slice(0, 4);
  return `${quoteIdn} / ${invNo}`;
}

function buildCargoPlaces(inv: InvoiceRowRaw): WorkspaceCargoPlace[] {
  return (inv.cargo_places ?? [])
    .map((cp) => ({
      position: cp.position,
      weightKg: cp.weight_kg,
      lengthMm: cp.length_mm,
      widthMm: cp.width_mm,
      heightMm: cp.height_mm,
    }))
    .sort((a, b) => a.position - b.position);
}

/**
 * Resolve per-domain timer / assignee fields off an invoice row.
 *
 * REQ-4: `assignedAt` falls back to `procurement_completed_at` (the
 * stage-entry timestamp) — NOT `created_at` — so an unassigned card still
 * shows a running timer counting from when the deal entered the stage.
 */
function domainFields(inv: InvoiceRowRaw, domain: WorkspaceDomain) {
  const stageEnteredAt = inv.procurement_completed_at ?? inv.created_at ?? "";
  if (domain === "logistics") {
    return {
      stageEnteredAt,
      assignedAt:
        inv.logistics_assigned_at ??
        inv.procurement_completed_at ??
        inv.created_at ??
        "",
      deadlineAt: inv.logistics_deadline_at,
      completedAt: inv.logistics_completed_at,
      assignedUserId: inv.assigned_logistics_user,
    };
  }
  return {
    stageEnteredAt,
    assignedAt:
      inv.customs_assigned_at ??
      inv.procurement_completed_at ??
      inv.created_at ??
      "",
    deadlineAt: inv.customs_deadline_at,
    completedAt: inv.customs_completed_at,
    assignedUserId: inv.assigned_customs_user,
  };
}

// ---------------------------------------------------------------------------
// Kanban fetcher
// ---------------------------------------------------------------------------

/**
 * Fetch the full kanban board for a domain — all three columns pre-populated.
 *
 * Visibility (REQ-5/6):
 *   - «Нераспределено» — every domain user sees all unassigned cards.
 *   - «В работе» — a member sees only their own; a head sees all.
 *   - «Завершено» — all users; capped at the last 100 / 90 days (Risk 4).
 *
 * Org scoping is enforced via the `quotes!inner` join (REQ-11).
 */
export async function fetchKanbanInvoices(
  domain: WorkspaceDomain,
  userId: string,
  orgId: string,
  isHead: boolean
): Promise<WorkspaceKanbanBoard> {
  const admin = createAdminClient();
  const completedCol =
    domain === "logistics"
      ? "logistics_completed_at"
      : "customs_completed_at";

  const ninetyDaysAgo = new Date(
    Date.now() - 90 * 24 * 60 * 60 * 1000
  ).toISOString();

  // Active rows: unassigned + in-progress. Gated on BOTH per-invoice
  // procurement completion AND the parent quote having actually transitioned
  // to the logistics+customs stage. Without the workflow_status filter, a
  // single completed КП of a multi-invoice quote would surface here while the
  // quote stage rail (correctly) still sits at pending_procurement.
  const activeQuery = admin
    .from("invoices")
    // Types on this branch lag migration 285 — runtime select is authoritative.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .select(INVOICE_COLUMNS as any)
    .eq("quote.organization_id", orgId)
    .eq("quote.workflow_status", "pending_logistics_and_customs")
    .is("quote.deleted_at", null)
    .is(completedCol, null)
    .not("procurement_completed_at", "is", null)
    .order("procurement_completed_at", { ascending: true, nullsFirst: false });

  // Completed rows: capped at the last 90 days, newest-first (Risk 4 — the
  // Завершено column would otherwise grow unbounded).
  const completedQuery = admin
    .from("invoices")
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    .select(INVOICE_COLUMNS as any)
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .not(completedCol, "is", null)
    .gte(completedCol, ninetyDaysAgo)
    .order(completedCol, { ascending: false })
    .limit(100);

  const [activeRes, completedRes] = await Promise.all([
    activeQuery,
    completedQuery,
  ]);

  if (activeRes.error) {
    console.error("fetchKanbanInvoices: active query failed", activeRes.error);
  }
  if (completedRes.error) {
    console.error(
      "fetchKanbanInvoices: completed query failed",
      completedRes.error
    );
  }

  const activeRows = (activeRes.data ?? []) as unknown as InvoiceRowRaw[];
  const completedRows = (completedRes.data ??
    []) as unknown as InvoiceRowRaw[];
  const allRows = [...activeRows, ...completedRows];

  if (allRows.length === 0) {
    return { unassigned: [], in_progress: [], completed: [] };
  }

  // Resolve item counts + assignee display info in a single round-trip each.
  const quoteIds = Array.from(new Set(allRows.map((r) => r.quote_id)));
  const userIds = allRows
    .map((r) => domainFields(r, domain).assignedUserId)
    .filter((id): id is string => !!id);

  const [itemMap, userMap] = await Promise.all([
    fetchItemCountsByQuoteId(admin, quoteIds),
    fetchUserMetaMap(admin, userIds),
  ]);

  function shape(inv: InvoiceRowRaw): WorkspaceKanbanCard {
    const fields = domainFields(inv, domain);
    const assignedUser = fields.assignedUserId
      ? userMap.get(fields.assignedUserId)
      : undefined;
    return {
      id: inv.id,
      quoteId: inv.quote_id,
      invoiceNumber: inv.invoice_number ?? inv.id.slice(0, 4),
      idn: buildInvoiceIdn(inv),
      quoteIdn: inv.quote?.idn_quote ?? "",
      customerName: inv.quote?.customer?.name ?? "—",
      customerId: inv.quote?.customer?.id ?? null,
      pickupLocation: buildPickupLocation(inv),
      deliveryLocation: buildDeliveryLocation(inv),
      stageEnteredAt: fields.stageEnteredAt,
      assignedAt: fields.assignedUserId ? inv[
        domain === "logistics"
          ? "logistics_assigned_at"
          : "customs_assigned_at"
      ] : null,
      deadlineAt: fields.deadlineAt,
      completedAt: fields.completedAt ?? null,
      assignedUserId: fields.assignedUserId,
      assignedUser,
      itemCount: itemMap.get(inv.quote_id) ?? 0,
      dealSumTotal: inv.quote?.total_amount ?? null,
      dealSumCurrency: inv.quote?.currency ?? "USD",
      totalWeightKg: inv.total_weight_kg,
      totalVolumeM3: inv.total_volume_m3,
      packageCount: inv.package_count,
      cargoPlaces: buildCargoPlaces(inv),
      // Pull only the distribution comment off `sales_checklist` — the rest of
      // the JSONB payload is consumed by the quote/deal context panel via its
      // own fetcher. Empty / whitespace-only values normalize to null so the
      // kanban-card render check is a simple truthy test.
      distributionComment:
        (inv.quote?.sales_checklist?.distribution_comment ?? "").trim().length >
        0
          ? inv.quote!.sales_checklist!.distribution_comment!.trim()
          : null,
    };
  }

  const board: WorkspaceKanbanBoard = {
    unassigned: [],
    in_progress: [],
    completed: [],
  };

  for (const inv of allRows) {
    const fields = domainFields(inv, domain);
    const column = deriveKanbanColumn({
      completedAt: fields.completedAt ?? null,
      assignedUserId: fields.assignedUserId,
    });
    // REQ-5/6: members see only their own «В работе» cards; heads see all.
    if (
      !isCardVisibleToUser(column, fields.assignedUserId, userId, isHead)
    ) {
      continue;
    }
    board[column].push(shape(inv));
  }

  return board;
}

// ---------------------------------------------------------------------------
// Team / stats (kept — consumed by the assignee picker + stats strip)
// ---------------------------------------------------------------------------

/**
 * fetchTeamUsers — resolves users with the given domain role in the org via
 * user_roles + the auth admin API. Used by the head's assignee picker.
 */
export async function fetchTeamUsers(
  domain: WorkspaceDomain,
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
 * Workspace-level KPI stats for the head/admin strip: active count, overdue
 * count, completed this ISO week, avg SLA hours over the last 30 completed.
 */
export async function fetchWorkspaceStats(
  domain: WorkspaceDomain,
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
    .not("procurement_completed_at", "is", null);

  const overdueQuery = admin
    .from("invoices")
    .select("id, quote:quotes!inner(organization_id, deleted_at)", {
      count: "exact",
      head: true,
    })
    .eq("quote.organization_id", orgId)
    .is("quote.deleted_at", null)
    .is(completedCol, null)
    .not("procurement_completed_at", "is", null)
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
    .select(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
