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

  // 1. Get pending_procurement quotes for this org (not deleted).
  //    Aligned with kanban + sidebar badge: distribution is only meaningful
  //    while the quote is in procurement. Quotes that already moved past
  //    procurement (e.g. pending_logistics_and_customs) may still have stale
  //    unassigned items, but they are not actionable from this screen.
  const { data: quoteRows } = await supabase
    .from("quotes")
    .select("id, idn_quote, customer_id, created_by_user_id, created_at")
    .eq("organization_id", orgId)
    .eq("workflow_status", "pending_procurement")
    .is("deleted_at", null);

  if (!quoteRows || quoteRows.length === 0) return [];

  const quoteIds = quoteRows.map((q) => q.id);

  // 2. Get unassigned, available items across all quotes. Mirrors the kanban
  //    drag-guard (`countUnassignedItems`): unavailable items don't need МОЗ
  //    assignment, so they shouldn't gate distribution either.
  const { data: items } = await supabase
    .from("quote_items")
    .select("id, quote_id, brand, product_name, quantity, created_at")
    .in("quote_id", quoteIds)
    .is("assigned_procurement_user", null)
    .neq("is_unavailable", true);

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
 * Distribution metrics shared by the sidebar badge, the page header, and the
 * kanban "Распределение" column. Derived from the single source-of-truth
 * `fetchDistributionData` so all three surfaces always agree.
 *
 * Units:
 *   - quoteCount:      unique quotes (заявки) — UX-friendly aggregate
 *   - brandSliceCount: distinct (quote × brand) pairs — matches the cards
 *                      rendered on the distribution page AND the kanban
 *                      "Распределение" column count (1 card = 1 brand slice)
 *   - itemCount:       total unassigned, available positions across all quotes
 */
export async function fetchDistributionMetrics(orgId: string): Promise<{
  quoteCount: number;
  brandSliceCount: number;
  itemCount: number;
}> {
  const quotes = await fetchDistributionData(orgId);
  const brandSliceCount = quotes.reduce(
    (sum, q) => sum + q.brandGroups.length,
    0
  );
  const itemCount = quotes.reduce(
    (sum, q) => sum + q.brandGroups.reduce((s, bg) => s + bg.itemCount, 0),
    0
  );
  return { quoteCount: quotes.length, brandSliceCount, itemCount };
}

/**
 * Sidebar badge count for "Распределение". Returns the brand-slice count
 * (= cards on the distribution page = kanban "Распределение" column count)
 * so the sidebar, page header, and kanban column never diverge when a quote
 * has 2+ brands at the distribution stage.
 */
export async function fetchUnassignedItemCount(orgId: string): Promise<number> {
  const { brandSliceCount } = await fetchDistributionMetrics(orgId);
  return brandSliceCount;
}
