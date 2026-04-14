import { createAdminClient } from "@/shared/lib/supabase/server";
import type {
  QuoteWithBrandGroups,
  QuoteInfo,
  BrandGroup,
} from "../model/types";

export async function fetchDistributionData(
  orgId: string
): Promise<QuoteWithBrandGroups[]> {
  const supabase = createAdminClient();

  // 1. Get all quotes for this org (not deleted)
  const { data: quoteRows } = await supabase
    .from("quotes")
    .select("id, idn_quote, customer_id, created_by_user_id, created_at")
    .eq("organization_id", orgId)
    .is("deleted_at", null)
    .not("workflow_status", "in", "(cancelled,rejected,draft)");

  if (!quoteRows || quoteRows.length === 0) return [];

  const quoteIds = quoteRows.map((q) => q.id);

  // 2. Get unassigned items across all quotes
  const { data: items } = await supabase
    .from("quote_items")
    .select("id, quote_id, brand, product_name, quantity, created_at")
    .in("quote_id", quoteIds)
    .is("assigned_procurement_user", null);

  if (!items || items.length === 0) return [];

  // 3. Find which quotes actually have unassigned items
  const quoteIdsWithItems = new Set(items.map((i) => i.quote_id));
  const relevantQuotes = quoteRows.filter((q) => quoteIdsWithItems.has(q.id));

  // 4. Batch-fetch customer names
  const customerIds = [
    ...new Set(
      relevantQuotes
        .map((q) => q.customer_id)
        .filter((id): id is string => id !== null)
    ),
  ];
  const customerMap = new Map<string, string>();
  if (customerIds.length > 0) {
    const { data: customers } = await supabase
      .from("customers")
      .select("id, name")
      .in("id", customerIds);
    for (const c of customers ?? []) {
      customerMap.set(c.id, c.name);
    }
  }

  // 5. Batch-fetch sales manager names
  const managerIds = [
    ...new Set(
      relevantQuotes
        .map((q) => q.created_by_user_id)
        .filter((id): id is string => id !== null)
    ),
  ];
  const managerMap = new Map<string, string | null>();
  if (managerIds.length > 0) {
    const { data: profiles } = await supabase
      .from("user_profiles")
      .select("user_id, full_name")
      .eq("organization_id", orgId)
      .in("user_id", managerIds);
    for (const p of profiles ?? []) {
      managerMap.set(p.user_id, p.full_name);
    }
  }

  // 6. Group items by quote, then by brand
  const itemsByQuote = new Map<string, typeof items>();
  for (const item of items) {
    const list = itemsByQuote.get(item.quote_id) ?? [];
    list.push(item);
    itemsByQuote.set(item.quote_id, list);
  }

  // 7. Build result sorted by quote created_at ASC (oldest first)
  const sorted = relevantQuotes.sort(
    (a, b) =>
      new Date(a.created_at ?? 0).getTime() -
      new Date(b.created_at ?? 0).getTime()
  );

  return sorted.map((q) => {
    const quoteItems = itemsByQuote.get(q.id) ?? [];

    // Group by normalized brand
    const brandMap = new Map<string, { itemCount: number; itemIds: string[] }>();
    for (const item of quoteItems) {
      const key = item.brand ? item.brand.toLowerCase() : "__null__";
      const group = brandMap.get(key) ?? { itemCount: 0, itemIds: [] };
      group.itemCount++;
      group.itemIds.push(item.id);
      brandMap.set(key, group);
    }

    // Sort brand groups: alphabetical, null-brand last
    const brandGroups: BrandGroup[] = [...brandMap.entries()]
      .sort(([a], [b]) => {
        if (a === "__null__") return 1;
        if (b === "__null__") return -1;
        return a.localeCompare(b);
      })
      .map(([key, group]) => ({
        brand: key === "__null__" ? null : (quoteItems.find(
          (i) => i.brand && i.brand.toLowerCase() === key
        )?.brand ?? key),
        itemCount: group.itemCount,
        itemIds: group.itemIds,
      }));

    const quote: QuoteInfo = {
      id: q.id,
      idn: q.idn_quote ?? "",
      customer_name: q.customer_id
        ? (customerMap.get(q.customer_id) ?? null)
        : null,
      sales_manager_name: q.created_by_user_id
        ? (managerMap.get(q.created_by_user_id) ?? null)
        : null,
      created_at: q.created_at,
    };

    return { quote, brandGroups };
  });
}

/**
 * Count of brand-slices currently in the `distributing` substatus for the
 * sidebar badge. Mirrors the kanban's "Распределение" column exactly: one
 * row per (quote, brand) slice where the quote is alive + pending_procurement
 * + in the user's org. Replaces the old item-level count so the sidebar and
 * kanban agree on the unit of work.
 */
export async function fetchUnassignedItemCount(orgId: string): Promise<number> {
  const supabase = createAdminClient();

  const { count } = await supabase
    .from("quote_brand_substates")
    .select("quote_id, quotes!inner(id)", { count: "exact", head: true })
    .eq("substatus", "distributing")
    .eq("quotes.workflow_status", "pending_procurement")
    .eq("quotes.organization_id", orgId)
    .is("quotes.deleted_at", null);

  return count ?? 0;
}
