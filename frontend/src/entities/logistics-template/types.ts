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
  /**
   * Optional concrete from-location id (m309 hybrid templates,
   * РОЛ Тест 07 #3.5). When set, apply_template uses this id directly;
   * otherwise it falls back to fromLocationType-based selection.
   */
  fromLocationId?: string;
  /** Optional concrete to-location id — see fromLocationId. */
  toLocationId?: string;
}

export interface LogisticsTemplate {
  id: string;
  name: string;
  description?: string;
  createdBy?: string;
  createdAt: string;
  segments: LogisticsTemplateSegment[];
}
