import { createClient } from "@/shared/lib/supabase/server";
import { isSalesOnly, isAssignedItemsOnly } from "@/shared/lib/roles";
import { getAssignedCustomerIds } from "@/shared/lib/access";

export interface ChatListItem {
  quoteId: string;
  idnQuote: string;
  customerName: string | null;
  lastMessageBody: string;
  lastMessageAt: string;
  lastMessageUserId: string;
  lastMessageUserName: string | null;
  commentCount: number;
}

export type ChatAccessUser = {
  id: string;
  roles: string[];
  orgId: string;
  salesGroupId?: string | null;
};

/**
 * Resolve quote IDs the user is **personally assigned** to (their "Мои КП"
 * scope), regardless of role.
 *
 * Includes:
 *   - quotes.created_by = self (МОП ownership)
 *   - quotes.assigned_logistics_user = self (МОЛ)
 *   - quotes.assigned_customs_user = self (МОТ)
 *   - quote_items.assigned_procurement_user = self (МОЗ — per-item)
 *
 * The "Мои КП" filter on /messages used to mean "quotes where I wrote the
 * last message", which excluded any chat where the user was a participant
 * but had not yet replied (МОЗ Тест 2026-05-01 fail #28). The correct
 * semantic — confirmed in triage — is: every quote where the user is a
 * responsible party.
 */
async function resolveMyAssignedQuoteIds(
  supabase: Awaited<ReturnType<typeof createClient>>,
  userId: string,
  orgId: string,
): Promise<Set<string>> {
  const [createdRes, logisticsRes, customsRes, procurementRes] =
    await Promise.all([
      supabase
        .from("quotes")
        .select("id")
        .eq("organization_id", orgId)
        .eq("created_by", userId)
        .is("deleted_at", null),
      supabase
        .from("quotes")
        .select("id")
        .eq("organization_id", orgId)
        .eq("assigned_logistics_user", userId)
        .is("deleted_at", null),
      supabase
        .from("quotes")
        .select("id")
        .eq("organization_id", orgId)
        .eq("assigned_customs_user", userId)
        .is("deleted_at", null),
      supabase
        .from("quote_items")
        .select("quote_id")
        .eq("assigned_procurement_user", userId),
    ]);

  const ids = new Set<string>();
  for (const r of createdRes.data ?? []) ids.add(r.id);
  for (const r of logisticsRes.data ?? []) ids.add(r.id);
  for (const r of customsRes.data ?? []) ids.add(r.id);
  for (const r of procurementRes.data ?? []) {
    if (r.quote_id) ids.add(r.quote_id);
  }
  return ids;
}

/**
 * Fetch quotes the user can chat on, sorted by most recent message
 * (quotes without messages still appear at the bottom — MoZ Тест fail #27
 * was that empty chats were filtered out by the comments-first query).
 *
 * "Мои КП" filter narrows to quotes the user is personally assigned to
 * (see {@link resolveMyAssignedQuoteIds} for the rule). "Все" is the
 * full role-scoped set.
 */
export async function fetchAllChats(
  user: ChatAccessUser,
  filter: "my" | "all" = "all"
): Promise<ChatListItem[]> {
  const supabase = await createClient();

  // Step 1: Determine which quotes the user can SEE at all (role-scoped).
  let quotesQuery = supabase
    .from("quotes")
    .select("id, idn_quote, customer_id, created_by")
    .eq("organization_id", user.orgId)
    .is("deleted_at", null);

  // Role-based filtering per .kiro/steering/access-control.md:
  // Sales users see chats on quotes they created OR on quotes whose customer
  // is assigned to them (or any group member for head_of_sales) via
  // customer_assignees.
  if (isSalesOnly(user.roles)) {
    const assignedCustomerIds = await getAssignedCustomerIds(supabase, user);

    if (assignedCustomerIds.length > 0) {
      quotesQuery = quotesQuery.or(
        `created_by.eq.${user.id},customer_id.in.(${assignedCustomerIds.join(",")})`
      );
    } else {
      quotesQuery = quotesQuery.eq("created_by", user.id);
    }
  } else if (isAssignedItemsOnly(user.roles)) {
    // Operational roles (procurement, logistics, customs) see chats only on
    // quotes where they are personally assigned. Procurement assignment lives
    // per-item on quote_items.assigned_procurement_user (single source of
    // truth — see .kiro/specs/procurement-users-single-source/).
    const { data: itemAssignedRows } = await supabase
      .from("quote_items")
      .select("quote_id")
      .eq("assigned_procurement_user", user.id);

    const procurementQuoteIds = Array.from(
      new Set(
        (itemAssignedRows ?? [])
          .map((r) => r.quote_id)
          .filter((id): id is string => !!id)
      )
    );

    const orClauses = [
      `assigned_logistics_user.eq.${user.id}`,
      `assigned_customs_user.eq.${user.id}`,
    ];
    if (procurementQuoteIds.length > 0) {
      orClauses.unshift(`id.in.(${procurementQuoteIds.join(",")})`);
    }

    quotesQuery = quotesQuery.or(orClauses.join(","));
  }

  // "Мои КП" filter — applies on top of the role-scoped set.
  if (filter === "my") {
    const myIds = await resolveMyAssignedQuoteIds(supabase, user.id, user.orgId);
    if (myIds.size === 0) return [];
    quotesQuery = quotesQuery.in("id", Array.from(myIds));
  }

  const { data: quotes, error: quotesError } = await quotesQuery;
  if (quotesError) throw quotesError;
  if (!quotes?.length) return [];

  // Step 2: Fetch comments only for the role-scoped quotes (cheap subset).
  const quoteIds = quotes.map((q) => q.id);
  const { data: commentsAgg, error: commentsError } = await supabase
    .from("quote_comments")
    .select("id, quote_id, user_id, body, created_at")
    .in("quote_id", quoteIds)
    .order("created_at", { ascending: false });

  if (commentsError) throw commentsError;

  // Aggregate per-quote: latest body/timestamp + total count.
  const quoteLastComment = new Map<
    string,
    { body: string; created_at: string; user_id: string; count: number }
  >();

  for (const c of commentsAgg ?? []) {
    const existing = quoteLastComment.get(c.quote_id);
    if (!existing) {
      quoteLastComment.set(c.quote_id, {
        body: c.body,
        created_at: c.created_at,
        user_id: c.user_id,
        count: 1,
      });
    } else {
      existing.count += 1;
    }
  }

  // Step 3: Batch-resolve customer names and user names
  const customerIds = Array.from(
    new Set(
      quotes.map((q) => q.customer_id).filter((id): id is string => id !== null)
    )
  );

  const lastMessageUserIds = Array.from(
    new Set(
      quotes
        .map((q) => quoteLastComment.get(q.id)?.user_id)
        .filter((id): id is string => id !== undefined)
    )
  );

  const [customersRes, usersRes] = await Promise.all([
    customerIds.length > 0
      ? supabase.from("customers").select("id, name").in("id", customerIds)
      : Promise.resolve({ data: [] as { id: string; name: string }[], error: null }),
    lastMessageUserIds.length > 0
      ? supabase
          .from("user_profiles")
          .select("user_id, full_name")
          .in("user_id", lastMessageUserIds)
      : Promise.resolve({
          data: [] as { user_id: string; full_name: string | null }[],
          error: null,
        }),
  ]);

  const customerMap = new Map(
    (customersRes.data ?? []).map((c) => [c.id, c.name])
  );
  const userMap = new Map(
    (usersRes.data ?? []).map((u) => [u.user_id, u.full_name])
  );

  // Step 4: Build result list. Empty chats (no messages yet) appear with an
  // empty body + null userId; sort puts them after non-empty chats by
  // falling back to "" timestamp, which compares as "older than any ISO
  // string". МОЗ Тест 2026-05-01 fail #27 was specifically that empty
  // chats were missing from "Все" — we now include them.
  const items: ChatListItem[] = quotes
    .map((q) => {
      const last = quoteLastComment.get(q.id);
      return {
        quoteId: q.id,
        idnQuote: q.idn_quote,
        customerName: q.customer_id ? customerMap.get(q.customer_id) ?? null : null,
        lastMessageBody: last?.body ?? "",
        lastMessageAt: last?.created_at ?? "",
        lastMessageUserId: last?.user_id ?? "",
        lastMessageUserName: last ? userMap.get(last.user_id) ?? null : null,
        commentCount: last?.count ?? 0,
      };
    })
    .sort(
      (a, b) =>
        new Date(b.lastMessageAt || 0).getTime() -
        new Date(a.lastMessageAt || 0).getTime()
    );

  return items;
}

/**
 * Fetch org members for @mention autocomplete.
 * Returns all active members with their full names.
 */
export async function fetchOrgMembers(
  orgId: string
): Promise<Array<{ userId: string; fullName: string }>> {
  const supabase = await createClient();

  const { data: members, error } = await supabase
    .from("organization_members")
    .select("user_id")
    .eq("organization_id", orgId)
    .eq("status", "active");

  if (error) throw error;
  if (!members?.length) return [];

  const userIds = members.map((m) => m.user_id);

  const { data: profiles } = await supabase
    .from("user_profiles")
    .select("user_id, full_name")
    .in("user_id", userIds)
    .order("full_name");

  return (profiles ?? [])
    .filter((p) => p.full_name)
    .map((p) => ({
      userId: p.user_id,
      fullName: p.full_name!,
    }));
}
