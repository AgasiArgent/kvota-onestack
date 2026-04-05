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

export interface QuoteContextData {
  salesChecklist: SalesChecklist | null;
  contactPerson: ContextPanelContact | null;
  salesManager: ContextPanelSalesManager | null;
  participants: ContextPanelParticipant[];
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
    .single();

  if (!quoteRow) {
    return {
      salesChecklist: null,
      contactPerson: null,
      salesManager: null,
      participants: [],
    };
  }

  const salesChecklist =
    (quoteRow.sales_checklist as SalesChecklist | null) ?? null;
  const contactPersonId = quoteRow.contact_person_id ?? null;
  const createdBy = quoteRow.created_by ?? null;

  // 2. Parallel: contact person, sales manager profile, workflow transitions
  const [contactRes, managerRes, transitionsRes] = await Promise.all([
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

  // 4. Batch-resolve actor names for the participants block
  const transitions = transitionsRes.data ?? [];
  const actorIds = [
    ...new Set(transitions.map((t) => t.actor_id).filter(Boolean)),
  ] as string[];

  const profileMap = new Map<string, string>();
  if (actorIds.length > 0) {
    const { data: profiles } = await supabase
      .from("user_profiles")
      .select("user_id, full_name")
      .in("user_id", actorIds);
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

  return {
    salesChecklist,
    contactPerson,
    salesManager,
    participants,
  };
}
