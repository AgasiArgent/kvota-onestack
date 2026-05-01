/**
 * Per-invoice procurement progress helper.
 *
 * Derives an "N/M КП закрыто" badge from the invoices belonging to a quote.
 * Replaces the legacy boolean `quote.procurement_completed_at` flag — the
 * lock now lives on each `invoice.procurement_completed_at`, and a quote
 * is "fully closed" only when every non-empty invoice has its closure
 * timestamp set.
 *
 * Empty invoices (no items) don't count toward the denominator: an empty
 * КП is a draft, not real procurement work.
 */
export interface ProcurementProgressInvoice {
  procurement_completed_at: string | null;
  /**
   * Number of supplier-side positions on this invoice. When 0 the invoice
   * is excluded from progress (empty draft). When unknown, pass `null`
   * and the invoice is treated as non-empty (counts toward the total).
   */
  items_count?: number | null;
}

export interface ProcurementProgress {
  completed: number;
  total: number;
  /**
   * Russian-language label suited for inline rendering:
   * - empty when there are no real invoices
   * - "Закупка завершена" when completed === total
   * - "N/M КП завершено" otherwise
   */
  label: string;
}

export function getProcurementProgress(
  invoices: ProcurementProgressInvoice[]
): ProcurementProgress {
  const real = invoices.filter((inv) => {
    if (inv.items_count == null) return true;
    return inv.items_count > 0;
  });
  const total = real.length;
  if (total === 0) return { completed: 0, total: 0, label: "" };

  const completed = real.filter(
    (inv) => inv.procurement_completed_at != null
  ).length;

  if (completed === total) {
    return { completed, total, label: "Закупка завершена" };
  }
  return { completed, total, label: `${completed}/${total} КП завершено` };
}
