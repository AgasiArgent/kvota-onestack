// @ts-nocheck
// TODO: remove @ts-nocheck after migrations 285-291 applied + `cd frontend && npm run db:types` regenerates Database types to include the new tables/columns.
import "server-only";
import { createAdminClient } from "@/shared/lib/supabase/server";
import type { LocationType } from "@/entities/location";

/**
 * logistics-template entity — read queries for Route Constructor
 * template picker and Admin Routing (future templates tab).
 *
 * Templates store location TYPES, not concrete locations — concrete
 * locations are chosen at apply-time by the logistician. See spec §3.13.
 *
 * Mutations go through /api/logistics/templates — see server-actions.ts.
 */

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

const ALLOWED_TYPES: readonly LocationType[] = [
  "supplier",
  "hub",
  "customs",
  "own_warehouse",
  "client",
];

function coerceType(raw: unknown): LocationType {
  return ALLOWED_TYPES.includes(raw as LocationType) ? (raw as LocationType) : "hub";
}

interface TemplateRow {
  id: string;
  name: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  segments:
    | {
        id: string;
        sequence_order: number;
        from_location_type: string;
        to_location_type: string;
        default_label: string | null;
        default_days: number | null;
      }[]
    | null;
}

function mapRow(r: TemplateRow): LogisticsTemplate {
  const rawSegments = r.segments ?? [];
  const segments = [...rawSegments]
    .sort((a, b) => a.sequence_order - b.sequence_order)
    .map((s) => ({
      id: s.id,
      sequenceOrder: s.sequence_order,
      fromLocationType: coerceType(s.from_location_type),
      toLocationType: coerceType(s.to_location_type),
      defaultLabel: s.default_label ?? undefined,
      defaultDays: s.default_days ?? undefined,
    }));
  return {
    id: r.id,
    name: r.name,
    description: r.description ?? undefined,
    createdBy: r.created_by ?? undefined,
    createdAt: r.created_at,
    segments,
  };
}

export async function fetchLogisticsTemplates(
  orgId: string,
): Promise<LogisticsTemplate[]> {
  const admin = createAdminClient();
  const { data, error } = await admin
    .from("logistics_route_templates")
    .select(
      `
      id, name, description, created_by, created_at,
      segments:logistics_route_template_segments (
        id, sequence_order,
        from_location_type, to_location_type,
        default_label, default_days
      )
    `,
    )
    .eq("organization_id", orgId)
    .order("name", { ascending: true });

  if (error) {
    // eslint-disable-next-line no-console
    console.error("[fetchLogisticsTemplates]", error);
    return [];
  }
  return (data ?? []).map(mapRow as (r: unknown) => LogisticsTemplate);
}
