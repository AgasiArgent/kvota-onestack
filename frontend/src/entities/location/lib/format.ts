import type { LocationType } from "../ui/location-chip";

/**
 * Client-safe shape of a single location option used by all pickers.
 * The canonical row comes from `queries.ts` (server-only); this mirror
 * lives here so client components can `import type` without dragging the
 * server-only Supabase admin client into their bundle.
 */
export interface LocationOption {
  id: string;
  country: string;
  iso2?: string;
  city?: string;
  type: LocationType;
}

/**
 * Russian display labels for the 5 supported location types.
 * Single source of truth — consumed by route-constructor pickers and any
 * other location selector. Keep keys in sync with `LocationType`.
 */
export const LOCATION_TYPE_LABEL: Record<LocationType, string> = {
  supplier: "Поставщики",
  hub: "Хабы",
  customs: "Таможня",
  own_warehouse: "Склады",
  client: "Клиенты",
};

/**
 * "Country · City" or just "Country" when city is absent.
 * Returns "—" only as a last resort when both are missing (data error).
 */
export function formatLocationLabel(loc: LocationOption): string {
  if (loc.city && loc.country) return `${loc.country} · ${loc.city}`;
  return loc.country || "—";
}
