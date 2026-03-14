import { createClient } from "@/shared/lib/supabase/client";

// ---------- Form data types ----------

export interface ContactFormData {
  name: string;
  last_name?: string;
  patronymic?: string;
  position?: string;
  email?: string;
  phone?: string;
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

  const { data: contact, error } = await supabase
    .from("customer_contacts")
    .insert({
      ...data,
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

  const { data: contact, error } = await supabase
    .from("customer_contacts")
    .update(data)
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
      customer_id: customerId,
      organization_id: organizationId,
      user_id: userId,
    })
    .select()
    .single();

  if (error) throw error;
  return call;
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
