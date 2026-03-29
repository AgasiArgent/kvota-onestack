import { createClient } from "@/shared/lib/supabase/server";

export interface SpecificationRow {
  id: string;
  quote_id: string;
  quote_version_id: string | null;
  contract_id: string | null;
  specification_number: string | null;
  sign_date: string | null;
  status: string;
  readiness_period: string | null;
  signed_scan_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CustomerContractRow {
  id: string;
  customer_id: string;
  contract_number: string;
  contract_date: string;
  status: string;
  next_specification_number: number;
}

export interface CustomerContactRow {
  id: string;
  customer_id: string;
  name: string;
  position: string | null;
  is_signatory: boolean | null;
}

export async function fetchSpecificationByQuote(
  quoteId: string
): Promise<SpecificationRow | null> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("specifications")
    .select("id, quote_id, quote_version_id, contract_id, specification_number, sign_date, status, readiness_period, signed_scan_url, created_at, updated_at")
    .eq("quote_id", quoteId)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) throw error;
  return data;
}

export async function fetchCustomerContracts(
  customerId: string
): Promise<CustomerContractRow[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("customer_contracts")
    .select("id, customer_id, contract_number, contract_date, status, next_specification_number")
    .eq("customer_id", customerId)
    .eq("status", "active")
    .order("contract_date", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function fetchCustomerContacts(
  customerId: string
): Promise<CustomerContactRow[]> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("customer_contacts")
    .select("id, customer_id, name, position, is_signatory")
    .eq("customer_id", customerId)
    .order("name");

  if (error) throw error;
  return data ?? [];
}
