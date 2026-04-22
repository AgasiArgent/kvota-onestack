export interface BrandAssignment {
  id: string;
  brand: string;
  user_id: string;
  user_full_name: string | null;
  user_email: string | null;
  created_at: string | null;
}

export interface GroupAssignment {
  id: string;
  sales_group_id: string;
  sales_group_name: string | null;
  user_id: string;
  user_full_name: string | null;
  user_email: string | null;
  created_at: string;
}

export interface TenderChainStep {
  id: string;
  step_order: number;
  user_id: string;
  role_label: string;
  user_full_name: string | null;
  user_email: string | null;
}

export interface UnassignedItem {
  id: string;
  quote_id: string;
  quote_idn: string;
  brand: string | null;
  customer_name: string | null;
  sales_manager_name: string | null;
  created_at: string | null;
}

export interface ProcurementUser {
  id: string;
  full_name: string | null;
  email: string;
}

export interface SalesGroup {
  id: string;
  name: string;
}

export type RoutingTab = "brands" | "groups" | "tender" | "unassigned" | "logistics";

export interface LogisticsTemplateAdmin {
  id: string;
  name: string;
  description: string | null;
  created_by: string | null;
  created_by_name: string | null;
  created_at: string;
  segments: Array<{
    id: string;
    sequence_order: number;
    from_location_type: string;
    to_location_type: string;
    default_label: string | null;
    default_days: number | null;
  }>;
}
