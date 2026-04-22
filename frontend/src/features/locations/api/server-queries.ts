import { createAdminClient } from "@/shared/lib/supabase/server";
import type { LocationListItem, LocationStats, LocationFilters } from "../model/types";
import type { LocationType } from "@/entities/location/ui/location-chip";

const ALLOWED_TYPES: readonly LocationType[] = [
  "supplier",
  "hub",
  "customs",
  "own_warehouse",
  "client",
];

function normaliseType(raw: unknown): LocationType {
  return ALLOWED_TYPES.includes(raw as LocationType)
    ? (raw as LocationType)
    : "hub";
}

export async function fetchLocations(
  orgId: string,
  filters: LocationFilters
): Promise<LocationListItem[]> {
  const supabase = createAdminClient();
  const { search = "", country = "", status = "", type = "" } = filters;

  let query = supabase
    .from("locations")
    .select("id, country, city, code, is_active, location_type")
    .eq("organization_id", orgId)
    .order("country")
    .order("city")
    .limit(200);

  if (search) {
    query = query.or(
      `code.ilike.%${search}%,city.ilike.%${search}%,country.ilike.%${search}%`
    );
  }
  if (country) {
    query = query.eq("country", country);
  }
  if (status === "active") {
    query = query.eq("is_active", true);
  } else if (status === "inactive") {
    query = query.eq("is_active", false);
  }
  if (type && ALLOWED_TYPES.includes(type as LocationType)) {
    query = query.eq("location_type", type);
  }

  const { data, error } = await query;
  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    country: row.country,
    city: row.city,
    code: row.code,
    is_active: row.is_active !== false,
    location_type: normaliseType((row as { location_type?: unknown }).location_type),
  }));
}

export async function fetchLocationStats(orgId: string): Promise<LocationStats> {
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("locations")
    .select("is_active")
    .eq("organization_id", orgId);

  if (error) throw error;

  const rows = data ?? [];
  return {
    total: rows.length,
    active: rows.filter((r) => r.is_active !== false).length,
  };
}

export async function fetchLocationCountries(orgId: string): Promise<string[]> {
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("locations")
    .select("country")
    .eq("organization_id", orgId)
    .order("country");

  if (error) throw error;

  const countries = data ?? [];
  return [...new Set(countries.map((r) => r.country))];
}
