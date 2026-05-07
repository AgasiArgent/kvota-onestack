/**
 * Client-safe type definitions for logistics-segment entity.
 *
 * Kept separate from `queries.ts` (which imports "server-only") so that
 * client components can `import type` without pulling the server-only
 * module into the browser bundle.
 */

export interface LogisticsSegmentLocationRef {
  id: string;
  country: string;
  iso2?: string;
  city?: string;
  type: "supplier" | "hub" | "customs" | "own_warehouse" | "client";
}

/**
 * The four currency codes the segment editor supports. Other places in
 * the system may use a wider set, but logistics costs are constrained to
 * these four (matches the DB CHECK constraint added in migration 309).
 */
export type SegmentCurrency = "RUB" | "USD" | "EUR" | "CNY";

export const SEGMENT_CURRENCIES: readonly SegmentCurrency[] = [
  "RUB",
  "USD",
  "EUR",
  "CNY",
];

export interface LogisticsSegmentExpense {
  id: string;
  label: string;
  /** Cost in `currencyCode` (column name kept for back-compat — m309). */
  costRub: number;
  currencyCode: SegmentCurrency;
  days?: number;
  notes?: string;
}

export interface LogisticsSegment {
  id: string;
  invoiceId: string;
  sequenceOrder: number;
  fromLocation?: LogisticsSegmentLocationRef;
  toLocation?: LogisticsSegmentLocationRef;
  label?: string;
  transitDays?: number;
  /** Main cost in `currencyCode` (column name kept for back-compat — m309). */
  mainCostRub: number;
  currencyCode: SegmentCurrency;
  carrier?: string;
  notes?: string;
  expenses: LogisticsSegmentExpense[];
}
