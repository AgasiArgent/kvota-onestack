/**
 * Pure helper for detecting MOQ (minimum order quantity) violations on a quote item row.
 *
 * A violation means the ordered `quantity` is strictly below the supplier's
 * declared `min_order_quantity`. Null values on either side suppress the warning
 * (incomplete data is not a violation).
 *
 * Extracted from `procurement-handsontable.tsx` so it can be unit-tested in
 * isolation and reused by the procurement-step totals badge.
 */
export interface MoqCheckable {
  quantity: number | null;
  min_order_quantity: number | null;
}

export function isMoqViolation(row: MoqCheckable): boolean {
  if (row.min_order_quantity == null) return false;
  if (row.quantity == null) return false;
  return row.quantity < row.min_order_quantity;
}

/**
 * Effective per-line quantity after applying the supplier MOQ floor
 * (Testing 2 row 85). Returns `max(quantity, minOrderQuantity)` when the MOQ
 * is a positive number strictly greater than the ordered quantity; otherwise
 * the ordered quantity unchanged. A null / 0 / negative MOQ is treated as "no
 * floor". Null `quantity` is treated as 0 for the comparison (so a positive
 * MOQ still binds). Mirrors the backend `effective_calc_quantity` helper so the
 * picker shows the same quantity the calc engine uses.
 */
export function effectiveQuantity(
  quantity: number | null,
  minOrderQuantity: number | null
): number {
  const ordered = quantity ?? 0;
  if (
    minOrderQuantity != null &&
    minOrderQuantity > 0 &&
    minOrderQuantity > ordered
  ) {
    return minOrderQuantity;
  }
  return ordered;
}
