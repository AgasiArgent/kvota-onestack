import { createClient } from "@/shared/lib/supabase/server";
import { SPECIFICATION_SELECT } from "./columns";

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
  // Реквизиты (requisites block — Req 2)
  our_legal_entity: string | null;
  client_legal_entity: string | null;
  /** FK → kvota.seller_companies (canonical "our legal entity"); migration 334. */
  seller_company_id: string | null;
  cargo_pickup_country: string | null;
  goods_shipment_country: string | null;
  supplier_payment_country: string | null;
  // Условия спецификации (conditions block — Req 3)
  validity_period: string | null;
  logistics_period: string | null;
  cargo_type: string | null;
  delivery_city_russia: string | null;
  // Контроль — at-signing FX (control stamp — Req 4); migration 334
  signing_fx_mode: string | null;
  signing_fx_rate: number | null;
  // Audit / signed scan
  created_by: string | null;
  signed_scan_document_id: string | null;
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
    .select(SPECIFICATION_SELECT)
    .eq("quote_id", quoteId)
    .is("deleted_at", null)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (error) throw error;
  // SPECIFICATION_SELECT is a runtime string, so supabase-js can't infer the row
  // shape from it (yields GenericStringError); SpecificationRow is the source of
  // truth for the columns we request. Cast through unknown to adopt it.
  return (data as unknown as SpecificationRow | null) ?? null;
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
