/**
 * Client-safe type definitions for logistics-template entity.
 *
 * Separate from `queries.ts` (server-only) — client components can
 * `import type` without pulling server-only modules into the browser bundle.
 */

import type { LocationType } from "@/entities/location/ui/location-chip";

export interface LogisticsTemplateSegment {
  id: string;
  sequenceOrder: number;
  fromLocationType: LocationType;
  toLocationType: LocationType;
  defaultLabel?: string;
  defaultDays?: number;
}

export interface LogisticsTemplate {
  id: string;
  name: string;
  description?: string;
  createdBy?: string;
  createdAt: string;
  segments: LogisticsTemplateSegment[];
}
