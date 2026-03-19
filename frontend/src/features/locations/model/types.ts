export interface LocationListItem {
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

export interface LocationStats {
  total: number;
  active: number;
  hubs: number;
  customs_points: number;
}

export interface LocationFilters {
  search?: string;
  country?: string;
  type?: string;
  status?: string;
}
