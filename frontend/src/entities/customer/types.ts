export interface Customer {
  id: string;
  name: string;
  inn: string | null;
  kpp: string | null;
  ogrn: string | null;
  legal_address: string | null;
  actual_address: string | null;
  postal_address: string | null;
  general_director_name: string | null;
  general_director_position: string | null;
  general_email: string | null;
  warehouse_addresses: { address: string; label?: string }[] | null;
  status: string;
  order_source: string | null;
  organization_id: string;
  manager_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  manager?: { full_name: string } | null;
  quotes_count?: number;
  specs_count?: number;
}

export interface PhoneEntry {
  number: string;
  ext: string | null;
  label: string;
}

export interface CustomerContact {
  id: string;
  customer_id: string;
  name: string;
  last_name: string | null;
  patronymic: string | null;
  position: string | null;
  email: string | null;
  phone: string | null;
  phones: PhoneEntry[];
  is_signatory: boolean;
  is_primary: boolean;
  is_lpr: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerListItem {
  id: string;
  name: string;
  inn: string | null;
  status: string;
  created_at: string;
  manager: { full_name: string } | null;
  quotes_count: number;
  last_quote_date: string | null;
}

export interface CustomerFinancials {
  customer_id: string;
  quotes_count: number;
  last_quote_date: string | null;
  specs_count: number;
  revenue_usd: number;
  profit_usd: number;
}

export interface CustomerCall {
  id: string;
  call_type: "call" | "scheduled";
  call_category: string | null;
  scheduled_date: string | null;
  comment: string | null;
  customer_needs: string | null;
  meeting_notes: string | null;
  contact_name: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  user_name: string | null;
  assigned_to: string | null;
  assigned_user_name?: string;
  created_at: string | null;
}

export interface CustomerContract {
  id: string;
  customer_id: string;
  organization_id: string;
  contract_number: string;
  contract_date: string | null;
  status: "active" | "suspended" | "terminated";
  notes: string | null;
  next_specification_number: number;
  created_at: string;
  updated_at: string;
}

export interface ContractFormData {
  contract_number: string;
  contract_date: string;
  status: "active" | "suspended" | "terminated";
  notes: string;
}

export interface CustomerStats {
  quotes_in_review: number;
  quotes_in_progress: number;
  quotes_total: number;
  specs_active: number;
  specs_signed: number;
  specs_total: number;
  total_debt: number;
  overdue_count: number;
  last_payment_date: string | null;
}
