import { createAdminClient } from "@/shared/lib/supabase/server";
import type { LocationListItem, LocationStats, LocationFilters } from "../model/types";

export async function fetchLocations(
  orgId: string,
  filters: LocationFilters
): Promise<LocationListItem[]> {
  const supabase = createAdminClient();
  const { search = "", country = "", status = "" } = filters;

  let query = supabase
    .from("locations")
    .select("id, country, city, code, is_active")
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

  const { data, error } = await query;
  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    country: row.country,
    city: row.city,
    code: row.code,
    is_active: row.is_active !== false,
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
