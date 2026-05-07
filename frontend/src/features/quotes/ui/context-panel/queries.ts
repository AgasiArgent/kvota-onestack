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
      logisticsAssignees: [],
      customsAssignees: [],
    };
  }

  const salesChecklist =
    (quoteRow.sales_checklist as SalesChecklist | null) ?? null;
  const contactPersonId = quoteRow.contact_person_id ?? null;
  const createdBy = quoteRow.created_by ?? null;

  // 2. Parallel: contact person, sales manager profile, workflow transitions,
  //    invoice-level МОЛ/МОТ assignments
  const [contactRes, managerRes, transitionsRes, invoicesRes] =
    await Promise.all([
      contactPersonId
        ? supabase
            .from("customer_contacts")
            .select("name, phone, email")
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
    ]);

  const contactPerson: ContextPanelContact | null = contactRes.data
    ? {
        name: contactRes.data.name,
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

  // 5. Batch-resolve all user names in one round-trip: transition actors +
  //    МОЛ + МОТ.
  const transitions = transitionsRes.data ?? [];
  const allUserIds = new Set<string>(
    transitions.map((t) => t.actor_id).filter(Boolean) as string[]
  );
  for (const id of logisticsAt.keys()) allUserIds.add(id);
  for (const id of customsAt.keys()) allUserIds.add(id);

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
    logisticsAssignees: buildAssignees(logisticsAt),
    customsAssignees: buildAssignees(customsAt),
  };
}
