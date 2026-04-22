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

export interface LogisticsSegmentExpense {
  id: string;
  label: string;
  costRub: number;
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
  mainCostRub: number;
  carrier?: string;
  notes?: string;
  expenses: LogisticsSegmentExpense[];
}
