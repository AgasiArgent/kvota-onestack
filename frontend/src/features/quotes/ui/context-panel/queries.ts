import { createClient, createAdminClient } from "@/shared/lib/supabase/server";
import type { SalesChecklist } from "./sales-checklist-block";

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
   * user_id and approximate «когда привязали» via the earliest workflow
   * transition that user is recorded on, since `quote_items` carries no
   * dedicated assignment timestamp.
   */
  procurementAssignees: ContextPanelDomainAssignee[];
  /** Distinct МОЛ assignees on this quote's invoices (РОЛ Тест 07 / 3.1). */
  logisticsAssignees: ContextPanelDomainAssignee[];
  /** Distinct МОТ assignees on this quote's invoices (РОЛ Тест 07 / 4.1). */
  customsAssignees: ContextPanelDomainAssignee[];
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
    };
  }

  const salesChecklist =
    (quoteRow.sales_checklist as SalesChecklist | null) ?? null;
  const contactPersonId = quoteRow.contact_person_id ?? null;
  const createdBy = quoteRow.created_by ?? null;

  // 2. Parallel: contact person, sales manager profile, workflow transitions,
  //    invoice-level МОЛ/МОТ assignments, item-level МОЗ assignment
  const [contactRes, managerRes, transitionsRes, invoicesRes, itemsRes] =
    await Promise.all([
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
        .select("assigned_procurement_user")
        .eq("quote_id", quoteId),
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
  //     dedicated assignment timestamp on `quote_items`; we leave the entry
  //     null here and back-fill the «когда привязали» moment from the user's
  //     earliest workflow_transitions row below (step 5). Testing 2 row 2.
  const items = itemsRes.data ?? [];
  const procurementAt = new Map<string, string | null>();
  for (const it of items) {
    const pUser = it.assigned_procurement_user ?? null;
    if (pUser && !procurementAt.has(pUser)) {
      procurementAt.set(pUser, null);
    }
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

  // Backfill МОЗ `assigned_at` with the earliest workflow_transitions row
  // recorded for that user on this quote, as a best-effort «когда привязали»
  // approximation. If the user has no transition (e.g., they only set the
  // per-item assignment without advancing the workflow), the timestamp stays
  // null and the panel renders the ФИО without a date — same as МОЛ/МОТ when
  // `*_assigned_at` is null.
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
  };
}
