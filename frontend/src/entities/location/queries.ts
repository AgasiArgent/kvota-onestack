import "server-only";
import { createAdminClient } from "@/shared/lib/supabase/server";
import type { LocationType } from "@/entities/location/ui/location-chip";

/**
 * Location queries — minimal shape for Route Constructor pickers
 * and Admin Routing dropdowns.
 *
 * Read-only; org-scoped via RLS + explicit filter (defense in depth).
 * Mutations live in admin-ops, not here.
 */

export interface LocationOption {
  id: string;
  country: string;
  iso2?: string;
  city?: string;
  type: LocationType;
}

interface LocationRow {
  id: string;
  country: string;
  city: string | null;
  location_type: string | null;
}

const ALLOWED_TYPES: readonly LocationType[] = [
  "supplier",
  "hub",
  "customs",
  "own_warehouse",
  "client",
];

function normaliseType(raw: string | null): LocationType {
  return ALLOWED_TYPES.includes(raw as LocationType) ? (raw as LocationType) : "hub";
}

function mapRow(r: LocationRow): LocationOption {
  return {
    id: r.id,
    country: r.country,
    city: r.city ?? undefined,
    type: normaliseType(r.location_type),
  };
}

/**
 * fetchLocations — all locations in org, sorted country → city.
 * Use for Route Constructor from/to pickers and admin patterns.
 */
export async function fetchLocations(orgId: string): Promise<LocationOption[]> {
  const admin = createAdminClient();
  const { data, error } = await admin
    .from("locations")
    .select("id, country, city, location_type")
    .eq("organization_id", orgId)
    .order("country", { ascending: true })
    .order("city", { ascending: true, nullsFirst: true });

  if (error) {
    // eslint-disable-next-line no-console
    console.error("[fetchLocations]", error);
    return [];
  }
  return (data ?? []).map(mapRow as (r: unknown) => LocationOption);
}

/**
 * fetchLocationsByTypes — picker variant filtered by allowed types.
 * Route Constructor uses this so that e.g. "from" picker in a supplier→hub
 * segment only offers suppliers.
 */
export async function fetchLocationsByTypes(
  orgId: string,
  types: LocationType[],
): Promise<LocationOption[]> {
  if (types.length === 0) return fetchLocations(orgId);
  const admin = createAdminClient();
  const { data, error } = await admin
    .from("locations")
    .select("id, country, city, location_type")
    .eq("organization_id", orgId)
    .in("location_type", types)
    .order("country", { ascending: true })
    .order("city", { ascending: true, nullsFirst: true });

  if (error) {
    // eslint-disable-next-line no-console
    console.error("[fetchLocationsByTypes]", error);
    return [];
  }
  return (data ?? []).map(mapRow as (r: unknown) => LocationOption);
}
