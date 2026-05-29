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
 * Effective per-line quantity. When the supplier quantity is set (non-null,
 * > 0) it OVERRIDES the ordered quantity in both directions; otherwise the
 * ordered quantity stands (null → 0). Mirrors the backend
 * `effective_calc_quantity` helper (same `> 0` rule).
 * (Supplier-quantity override, 2026-05-29 — supersedes the Row 85 max floor.)
 */
export function effectiveQuantity(
  ordered: number | null,
  supplierQty: number | null
): number {
  if (supplierQty != null && supplierQty > 0) return supplierQty;
  return ordered ?? 0;
}
