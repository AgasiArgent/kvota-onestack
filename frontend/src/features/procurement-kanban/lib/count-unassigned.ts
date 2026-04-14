import { createClient } from "@/shared/lib/supabase/client";

/**
 * Minimal shape of the Supabase query chain used by
 * `countUnassignedItems`. Kept loose on purpose so tests can pass a mock
 * builder without reproducing the full generated Database types.
 */
export interface UnassignedCountQueryBuilder {
  from: (table: string) => {
    select: (
      columns: string,
      opts: { count: "exact"; head: true }
    ) => CountChain;
  };
}
interface CountChain {
  eq: (column: string, value: unknown) => CountChain;
  is: (column: string, value: null) => CountChain;
  neq: (column: string, value: unknown) => CountChain;
  then: Promise<{ count: number | null }>["then"];
}

/**
 * Counts unassigned, non-unavailable items for a (quote, brand) slice. Used
 * by the kanban drag-guard before a transition out of "distributing" and by
 * tests to verify the guard behavior.
 *
 * Kanban stores unbranded cards with `brand === ""`, but the database column
 * uses `NULL` — normalize here.
 */
export async function countUnassignedItems(
  quoteId: string,
  brand: string,
  clientFactory: () => UnassignedCountQueryBuilder = createClient as unknown as () => UnassignedCountQueryBuilder
): Promise<number> {
  const supabase = clientFactory();
  const normalizedBrand: string | null = brand === "" ? null : brand;

  let query = supabase
    .from("quote_items")
    .select("id", { count: "exact", head: true })
    .eq("quote_id", quoteId)
    .is("assigned_procurement_user", null)
    .neq("is_unavailable", true);

  query =
    normalizedBrand === null
      ? query.is("brand", null)
      : query.eq("brand", normalizedBrand);

  const { count } = await (query as unknown as Promise<{
    count: number | null;
  }>);
  return count ?? 0;
}
