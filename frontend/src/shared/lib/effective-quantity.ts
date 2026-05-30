/**
 * Effective per-line quantity. When the supplier quantity is set (non-null,
 * > 0) it OVERRIDES the ordered quantity in both directions; otherwise the
 * ordered quantity stands (null → 0). Mirrors the backend
 * `effective_calc_quantity` helper (same `> 0` rule). Single in-app definition
 * of the supplier-quantity override rule (2026-05-29); lives in `shared` so
 * every FSD layer (entities, features) can import it.
 */
export function effectiveQuantity(
  ordered: number | null,
  supplierQty: number | null
): number {
  if (supplierQty != null && supplierQty > 0) return supplierQty;
  return ordered ?? 0;
}
