import type { createClient } from "./supabase/server";
import { isHeadOfSales } from "./roles";

type Client = Awaited<ReturnType<typeof createClient>>;

/**
 * Access control helpers for entity-level visibility.
 * Authoritative rules live in .kiro/steering/access-control.md.
 *
 * These helpers resolve a sales-user's scope in terms of customer IDs they
 * can see. Query functions then use the result to filter lists (via `.in()`)
 * or check detail access (via `.includes()`).
 */

type AccessUser = {
  id: string;
  salesGroupId?: string | null;
  orgId: string;
  roles: string[];
};

/**
 * Returns the set of user IDs whose customers the given user can see.
 * - Regular sales → just themselves
 * - Head of sales with a group → all group members (including themselves)
 * - Head of sales without a group → fallback to self
 */
async function resolveScopedUserIds(
  supabase: Client,
  user: AccessUser
): Promise<string[]> {
  if (!isHeadOfSales(user.roles) || !user.salesGroupId) {
    return [user.id];
  }

  const { data } = await supabase
    .from("user_profiles")
    .select("user_id")
    .eq("sales_group_id", user.salesGroupId)
    .eq("organization_id", user.orgId);

  const memberIds = (data ?? []).map((r) => r.user_id);
  return memberIds.length > 0 ? memberIds : [user.id];
}

/**
 * Returns the list of customer IDs the user is assigned to (directly, or
 * via group members if they are a head of sales).
 *
 * Used by:
 * - fetchCustomersList / canAccessCustomer
 * - fetchQuotesList / canAccessQuote / fetchFilterOptions
 *
 * Returns an empty array if the user has no assignments — callers should
 * handle this by scoping to zero rows (or falling back to created_by only
 * for quotes).
 */
export async function getAssignedCustomerIds(
  supabase: Client,
  user: AccessUser
): Promise<string[]> {
  const userIds = await resolveScopedUserIds(supabase, user);

  const { data } = await supabase
    .from("customer_assignees")
    .select("customer_id")
    .in("user_id", userIds);

  return (data ?? []).map((r) => r.customer_id);
}

/**
 * Returns the list of quote IDs that have items assigned to this user.
 * Used by ASSIGNED_ITEMS tier (procurement, logistics, customs).
 *
 * - procurement: via quote_items.assigned_procurement_user
 * - logistics: via quotes.assigned_logistics_user
 * - customs: via quotes.assigned_customs_user
 *
 * Runs applicable queries in parallel and deduplicates results.
 */
export async function getAssignedQuoteIds(
  supabase: Client,
  user: AccessUser
): Promise<string[]> {
  const promises: Promise<string[]>[] = [];

  if (user.roles.includes("procurement")) {
    promises.push(
      (async () => {
        const { data } = await supabase
          .from("quote_items")
          .select("quote_id")
          .eq("assigned_procurement_user", user.id);
        return [
          ...new Set(
            (data ?? [])
              .map((r) => r.quote_id)
              .filter((id): id is string => id !== null)
          ),
        ];
      })()
    );
  }

  if (user.roles.includes("logistics")) {
    promises.push(
      (async () => {
        const { data } = await supabase
          .from("quotes")
          .select("id")
          .eq("organization_id", user.orgId)
          .eq("assigned_logistics_user", user.id)
          .is("deleted_at", null);
        return (data ?? []).map((r) => r.id);
      })()
    );
  }

  if (user.roles.includes("customs")) {
    promises.push(
      (async () => {
        const { data } = await supabase
          .from("quotes")
          .select("id")
          .eq("organization_id", user.orgId)
          .eq("assigned_customs_user", user.id)
          .is("deleted_at", null);
        return (data ?? []).map((r) => r.id);
      })()
    );
  }

  if (promises.length === 0) return [];

  const results = await Promise.all(promises);
  return [...new Set(results.flat())];
}

/**
 * Returns the list of supplier IDs the user is assigned to.
 * Simpler than customer version — no group logic (head_of_procurement
 * sees all suppliers, so this is only called for regular procurement users).
 *
 * Returns an empty array if the user has no assignments — callers should
 * handle this by scoping to zero rows.
 */
export async function getAssignedSupplierIds(
  supabase: Client,
  userId: string
): Promise<string[]> {
  const { data } = await supabase
    .from("supplier_assignees")
    .select("supplier_id")
    .eq("user_id", userId);

  return (data ?? []).map((r) => r.supplier_id);
}
