/**
 * Items-table arithmetic helpers.
 *
 * Mirrors `services/kp_export.py:calc_row_total` / `calc_grand_total`:
 * - A row contributes to the total only when BOTH qty and price parse to
 *   finite numbers (REQ-4.7).
 * - `calcRowTotal` returns null on invalid input so the renderer can leave
 *   the per-row "Сумма" cell blank (REQ-4.5).
 * - `calcGrandTotal` silently skips invalid rows.
 */

import type { KpItem } from "../model/types";

function toNumber(value: string | undefined | null): number | null {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  if (raw === "") return null;

  const cleaned = raw
    .replace(/\s/g, "")
    .replace(/ /g, "")
    .replace(/ /g, "")
    .replace(",", ".");

  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}

export function calcRowTotal(item: KpItem): number | null {
  const qty = toNumber(item.qty);
  const price = toNumber(item.price);
  if (qty === null || price === null) return null;
  return qty * price;
}

export function calcGrandTotal(items: KpItem[]): number {
  let total = 0;
  for (const item of items) {
    const rowTotal = calcRowTotal(item);
    if (rowTotal !== null) total += rowTotal;
  }
  return total;
}
