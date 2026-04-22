import type { LocationType } from "@/entities/location/ui/location-chip";

export interface LocationListItem {
  id: string;
  country: string;
  city: string | null;
  code: string | null;
  is_active: boolean;
  location_type: LocationType;
}

export interface LocationStats {
  total: number;
  active: number;
}

export interface LocationFilters {
  search?: string;
  country?: string;
  status?: string;
  type?: string;
}
