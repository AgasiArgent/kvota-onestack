import { createAdminClient } from "@/shared/lib/supabase/server";
import type { LocationListItem, LocationStats, LocationFilters } from "../model/types";

/**
 * locations table has columns (is_hub, is_customs_point, address, display_name, notes)
 * not yet in generated DB types. Use untyped client for these queries.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedClient = { from: (table: string) => any };

function getUntypedClient(): UntypedClient {
  return createAdminClient() as unknown as UntypedClient;
}

interface LocationRow {
  id: string;
  country: string;
  city: string | null;
  code: string | null;
  address: string | null;
  is_hub: boolean;
  is_customs_point: boolean;
  is_active: boolean;
  display_name: string | null;
}

export async function fetchLocations(
  orgId: string,
  filters: LocationFilters
): Promise<LocationListItem[]> {
  const untyped = getUntypedClient();
  const { search = "", country = "", type = "", status = "" } = filters;

  let query = untyped
    .from("locations")
    .select("id, country, city, code, address, is_hub, is_customs_point, is_active, display_name")
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
  if (type === "hub") {
    query = query.eq("is_hub", true);
  } else if (type === "customs") {
    query = query.eq("is_customs_point", true);
  }
  if (status === "active") {
    query = query.eq("is_active", true);
  } else if (status === "inactive") {
    query = query.eq("is_active", false);
  }

  const { data, error } = await query;
  if (error) throw error;

  return ((data ?? []) as LocationRow[]).map((row) => ({
    id: row.id,
    country: row.country,
    city: row.city,
    code: row.code,
    address: row.address,
    is_hub: row.is_hub ?? false,
    is_customs_point: row.is_customs_point ?? false,
    is_active: row.is_active !== false,
    display_name: row.display_name,
  }));
}

export async function fetchLocationStats(orgId: string): Promise<LocationStats> {
  const untyped = getUntypedClient();
  const { data, error } = await untyped
    .from("locations")
    .select("is_active, is_hub, is_customs_point")
    .eq("organization_id", orgId);

  if (error) throw error;

  const rows = (data ?? []) as Array<{
    is_active: boolean;
    is_hub: boolean;
    is_customs_point: boolean;
  }>;

  return {
    total: rows.length,
    active: rows.filter((r) => r.is_active !== false).length,
    hubs: rows.filter((r) => r.is_hub).length,
    customs_points: rows.filter((r) => r.is_customs_point).length,
  };
}

export async function fetchLocationCountries(orgId: string): Promise<string[]> {
  const untyped = getUntypedClient();
  const { data, error } = await untyped
    .from("locations")
    .select("country")
    .eq("organization_id", orgId)
    .order("country");

  if (error) throw error;

  const countries = (data ?? []) as Array<{ country: string }>;
  return [...new Set(countries.map((r) => r.country))];
}
