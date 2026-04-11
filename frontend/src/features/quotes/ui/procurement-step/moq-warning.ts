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
