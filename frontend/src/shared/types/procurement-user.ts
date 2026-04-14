/**
 * Procurement user with current workload (counted in active quotes, not items).
 * Shared across distribution and kanban features — lives in shared/types so
 * both feature slices can consume it without cross-slice imports.
 */
export interface ProcurementUserWorkload {
  user_id: string;
  full_name: string | null;
  active_quotes: number;
}
