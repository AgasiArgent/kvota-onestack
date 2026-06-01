/**
 * Pure helpers for the /suppliers filter bar (Testing 2 row 92).
 *
 * The suppliers list filters (Страна / МОЗ / Бренд) are applied at the query
 * level so they narrow ACROSS all paginated pages, not just the 50 rows the
 * client happens to have loaded.
 *
 * Страна is a direct column on `suppliers`, so it filters inline. МОЗ and
 * Бренд live in junction tables (`supplier_assignees`, `brand_supplier_assignments`),
 * so each is resolved to a set of matching supplier IDs and the sets are
 * intersected (AND semantics) before being applied via `.in("id", …)`.
 *
 * These functions are extracted from `queries.ts` so the AND-intersection
 * logic can be unit-tested without a Supabase round-trip.
 */

/**
 * Intersect any number of supplier-id constraint sets. A `null` constraint
 * means "no filter from this source" and is skipped. Returns:
 *   - `null` when no constraint applied (caller should not add an `.in()` filter)
 *   - an array (possibly empty) of the IDs that satisfy EVERY applied constraint
 *
 * An empty intersection (e.g. a brand with no suppliers) yields `[]` — callers
 * must translate that into a zero-row query, never an unfiltered one.
 */
export function intersectSupplierIdConstraints(
  constraints: ReadonlyArray<readonly string[] | null>
): string[] | null {
  const applied = constraints.filter(
    (c): c is readonly string[] => c !== null
  );
  if (applied.length === 0) return null;

  let acc: Set<string> | null = null;
  for (const ids of applied) {
    const next = new Set<string>(ids);
    if (acc === null) {
      acc = next;
    } else {
      const current: Set<string> = acc;
      acc = new Set<string>([...current].filter((id) => next.has(id)));
    }
  }
  return acc === null ? [] : [...acc];
}
