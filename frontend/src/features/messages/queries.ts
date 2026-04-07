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
 * Fetch all quotes that have comments, sorted by most recent message.
 * Each item includes last message preview and quote metadata.
 */
export async function fetchAllChats(
  user: ChatAccessUser,
  filter: "my" | "all" = "all"
): Promise<ChatListItem[]> {
  const supabase = await createClient();

  // Step 1: Get quotes with comments — aggregate comment data
  // We query quote_comments grouped by quote_id to get last message info
  const { data: commentsAgg, error: commentsError } = await supabase
    .from("quote_comments")
    .select("id, quote_id, user_id, body, created_at")
    .order("created_at", { ascending: false });

  if (commentsError) throw commentsError;
  if (!commentsAgg?.length) return [];

  // Group by quote_id, keep only the latest comment per quote
  const quoteLastComment = new Map<
    string,
    { body: string; created_at: string; user_id: string; count: number }
  >();

  for (const c of commentsAgg) {
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

  const quoteIds = Array.from(quoteLastComment.keys());

  // Step 2: Fetch quotes metadata (filter by org)
  let quotesQuery = supabase
    .from("quotes")
    .select("id, idn_quote, customer_id, created_by")
    .eq("organization_id", user.orgId)
    .is("deleted_at", null)
    .in("id", quoteIds);

  if (filter === "my") {
    quotesQuery = quotesQuery.or(`created_by.eq.${user.id}`);
  }

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
    // quotes where they are personally assigned.
    quotesQuery = quotesQuery.or(
      `assigned_procurement_users.cs.{${user.id}},assigned_logistics_user.eq.${user.id},assigned_customs_user.eq.${user.id}`
    );
  }

  const { data: quotes, error: quotesError } = await quotesQuery;
  if (quotesError) throw quotesError;
  if (!quotes?.length) return [];

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

  // Step 4: Build result list sorted by last message time
  const items: ChatListItem[] = quotes
    .map((q) => {
      const last = quoteLastComment.get(q.id);
      if (!last) return null;

      return {
        quoteId: q.id,
        idnQuote: q.idn_quote,
        customerName: q.customer_id ? customerMap.get(q.customer_id) ?? null : null,
        lastMessageBody: last.body,
        lastMessageAt: last.created_at,
        lastMessageUserId: last.user_id,
        lastMessageUserName: userMap.get(last.user_id) ?? null,
        commentCount: last.count,
      };
    })
    .filter((item): item is ChatListItem => item !== null)
    .sort(
      (a, b) =>
        new Date(b.lastMessageAt).getTime() - new Date(a.lastMessageAt).getTime()
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
