export interface SupplierListItem {
  id: string;
  name: string;
  supplier_code: string | null;
  country: string | null;
  city: string | null;
  registration_number: string | null;
  is_active: boolean;
  primary_contact_name: string | null;
  primary_contact_email: string | null;
}

export interface SupplierDetail {
  id: string;
  organization_id: string;
  name: string;
  supplier_code: string | null;
  country: string | null;
  city: string | null;
  registration_number: string | null;
  default_payment_terms: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

export interface SupplierContact {
  id: string;
  supplier_id: string;
  name: string;
  position: string | null;
  email: string | null;
  phone: string | null;
  is_primary: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface BrandAssignment {
  id: string;
  brand: string;
  supplier_id: string;
  is_primary: boolean;
  notes: string | null;
  created_at: string | null;
}
