import { createClient } from "@/shared/lib/supabase/client";
import type { ContractFormData, CustomerContract, PhoneEntry } from "./types";

// ---------- Form data types ----------

export interface ContactFormData {
  name: string;
  last_name?: string;
  patronymic?: string;
  position?: string;
  email?: string;
  phone?: string;
  phones?: PhoneEntry[];
  is_signatory?: boolean;
  is_primary?: boolean;
  is_lpr?: boolean;
  notes?: string;
}

export interface CallFormData {
  call_type: "call" | "scheduled";
  call_category?: string;
  scheduled_date?: string;
  contact_person_id?: string;
  assigned_to?: string;
  comment?: string;
  customer_needs?: string;
  meeting_notes?: string;
}

export interface AddressFormData {
  legal_address?: string;
  actual_address?: string;
  postal_address?: string;
}

// ---------- Helpers ----------

async function getCustomerOrgId(customerId: string): Promise<string> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("customers")
    .select("organization_id")
    .eq("id", customerId)
    .single();

  if (error || !data?.organization_id) {
    throw new Error("Failed to resolve organization for customer");
  }
  return data.organization_id;
}

async function getCurrentUserId(): Promise<string> {
  const supabase = createClient();
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) {
    throw new Error("Not authenticated");
  }
  return user.id;
}

// ---------- Contact mutations ----------

export async function createContact(
  customerId: string,
  data: ContactFormData
) {
  const supabase = createClient();
  const organizationId = await getCustomerOrgId(customerId);

  const phonesArr = data.phones ?? [];
  const primaryPhone = phonesArr[0]?.number ?? data.phone ?? null;
  const phonesJson = JSON.parse(JSON.stringify(phonesArr));

  const { data: contact, error } = await supabase
    .from("customer_contacts")
    .insert({
      name: data.name,
      last_name: data.last_name ?? null,
      patronymic: data.patronymic ?? null,
      position: data.position ?? null,
      email: data.email ?? null,
      phone: primaryPhone,
      phones: phonesJson,
      is_signatory: data.is_signatory ?? false,
      is_primary: data.is_primary ?? false,
      is_lpr: data.is_lpr ?? false,
      notes: data.notes ?? null,
      customer_id: customerId,
      organization_id: organizationId,
    })
    .select()
    .single();

  if (error) throw error;
  return contact;
}

export async function updateContact(
  contactId: string,
  data: ContactFormData
) {
  const supabase = createClient();

  const phonesArr = data.phones ?? [];
  const primaryPhone = phonesArr[0]?.number ?? data.phone ?? null;
  const phonesJson = JSON.parse(JSON.stringify(phonesArr));

  const { data: contact, error } = await supabase
    .from("customer_contacts")
    .update({
      name: data.name,
      last_name: data.last_name ?? null,
      patronymic: data.patronymic ?? null,
      position: data.position ?? null,
      email: data.email ?? null,
      phone: primaryPhone,
      phones: phonesJson,
      is_signatory: data.is_signatory ?? false,
      is_primary: data.is_primary ?? false,
      is_lpr: data.is_lpr ?? false,
      notes: data.notes ?? null,
    })
    .eq("id", contactId)
    .select()
    .single();

  if (error) throw error;
  return contact;
}

export async function deleteContact(contactId: string) {
  const supabase = createClient();

  const { error } = await supabase
    .from("customer_contacts")
    .delete()
    .eq("id", contactId);

  if (error) throw error;
}

// ---------- Call mutations ----------

export async function createCall(
  customerId: string,
  data: CallFormData
) {
  const supabase = createClient();
  const [organizationId, userId] = await Promise.all([
    getCustomerOrgId(customerId),
    getCurrentUserId(),
  ]);

  const { data: call, error } = await supabase
    .from("calls")
    .insert({
      ...data,
      assigned_to: data.assigned_to || null,
      customer_id: customerId,
      organization_id: organizationId,
      user_id: userId,
    })
    .select()
    .single();

  if (error) throw error;
  return call;
}

export async function updateCall(
  callId: string,
  data: Partial<CallFormData>
) {
  const supabase = createClient();
  const { error } = await supabase
    .from("calls")
    .update(data)
    .eq("id", callId);
  if (error) throw error;
}

// ---------- Customer creation ----------

export async function createCustomer(
  orgId: string,
  data: { name: string; inn?: string }
): Promise<{ id: string }> {
  const supabase = createClient();
  const userId = await getCurrentUserId();

  const { data: customer, error } = await supabase
    .from("customers")
    .insert({
      name: data.name,
      inn: data.inn || null,
      organization_id: orgId,
      status: "active",
      created_by: userId,
    })
    .select("id")
    .single();

  if (error) throw error;
  return customer;
}

// ---------- Customer field mutations ----------

export async function updateCustomerNotes(
  customerId: string,
  notes: string
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("customers")
    .update({ notes })
    .eq("id", customerId);

  if (error) throw error;
}

export async function updateCustomerAddresses(
  customerId: string,
  data: AddressFormData
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("customers")
    .update(data)
    .eq("id", customerId);

  if (error) throw error;
}

// ---------- General email mutation ----------

export async function updateCustomerGeneralEmail(
  customerId: string,
  email: string
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("customers")
    .update({ general_email: email || null })
    .eq("id", customerId);

  if (error) throw error;
}

// ---------- Contract mutations ----------

export async function createContract(
  customerId: string,
  data: ContractFormData
): Promise<CustomerContract> {
  const supabase = createClient();
  const organizationId = await getCustomerOrgId(customerId);

  const { data: contract, error } = await supabase
    .from("customer_contracts")
    .insert({
      customer_id: customerId,
      organization_id: organizationId,
      contract_number: data.contract_number,
      contract_date: data.contract_date || new Date().toISOString().split("T")[0],
      status: data.status,
      notes: data.notes ?? null,
    })
    .select()
    .single();

  if (error) throw error;
  return contract as unknown as CustomerContract;
}

export async function updateContract(
  contractId: string,
  data: ContractFormData
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("customer_contracts")
    .update({
      contract_number: data.contract_number,
      contract_date: data.contract_date ?? null,
      status: data.status,
      notes: data.notes ?? null,
    })
    .eq("id", contractId);

  if (error) throw error;
}

export async function deleteContract(contractId: string) {
  const supabase = createClient();

  const { error } = await supabase
    .from("customer_contracts")
    .delete()
    .eq("id", contractId);

  if (error) throw error;
}
