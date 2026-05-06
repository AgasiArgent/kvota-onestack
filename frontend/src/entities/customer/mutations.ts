import { createClient } from "@/shared/lib/supabase/client";
import type { ContractFormData, CustomerContract, PhoneEntry } from "./types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedClient = { from: (table: string) => any };

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

export interface CreateCustomerData {
  name: string;
  inn?: string;
  kpp?: string;
  ogrn?: string;
  legal_address?: string;
}

export async function createCustomer(
  orgId: string,
  data: CreateCustomerData
): Promise<{ id: string }> {
  const supabase = createClient();
  const userId = await getCurrentUserId();

  const { data: customer, error } = await supabase
    .from("customers")
    .insert({
      name: data.name,
      inn: data.inn || null,
      kpp: data.kpp || null,
      ogrn: data.ogrn || null,
      legal_address: data.legal_address || null,
      organization_id: orgId,
      status: "active",
      created_by: userId,
      manager_id: userId,
    })
    .select("id")
    .single();

  if (error) throw error;

  // Auto-assign the creator. Without this row the customer-list filter
  // (``customer_assignees.user_id = self``) excludes МОП/РОП-created
  // customers from their own list, even though they appear as manager.
  // Best-effort: if the assignee insert fails, the customer itself is
  // already saved — surface a non-fatal warning rather than rolling back.
  const untyped = supabase as unknown as UntypedClient;
  const { error: assigneeError } = await untyped
    .from("customer_assignees")
    .insert({
      customer_id: customer.id,
      user_id: userId,
      created_by: userId,
    });
  if (assigneeError) {
    console.error(
      "[createCustomer] failed to auto-assign creator:",
      assigneeError
    );
  }

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

// ---------- Delivery address mutations ----------

export async function createDeliveryAddress(
  customerId: string,
  data: { name?: string; address: string }
): Promise<{ id: string; name: string | null; address: string }> {
  const supabase = createClient();
  const organizationId = await getCustomerOrgId(customerId);

  const { data: row, error } = await supabase
    .from("customer_delivery_addresses")
    .insert({
      customer_id: customerId,
      organization_id: organizationId,
      name: data.name ?? null,
      address: data.address,
    })
    .select("id, name, address")
    .single();

  if (error) throw error;
  return row as { id: string; name: string | null; address: string };
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

// ---------- Customer document upload ----------

export interface CustomerDocumentRow {
  id: string;
  storage_path: string;
  original_filename: string;
  file_size_bytes: number | null;
  mime_type: string | null;
  description: string | null;
  created_at: string | null;
}

/**
 * Upload a file to Supabase Storage and insert a kvota.documents row tied
 * to a customer. Used by both the contract modal (МОП-7) and the
 * Уставные документы section (МОП-8).
 *
 * `documentType` narrows the kind: 'contract' for contract scans,
 * 'founding_docs' for charter / registration docs. `description` is
 * displayed as a sub-label and is optional.
 */
export async function uploadCustomerDocument(
  customerId: string,
  file: File,
  documentType: "contract" | "founding_docs",
  description?: string
): Promise<CustomerDocumentRow> {
  const supabase = createClient();
  const [organizationId, userId] = await Promise.all([
    getCustomerOrgId(customerId),
    getCurrentUserId(),
  ]);

  const ext = file.name.split(".").pop()?.toLowerCase() || "bin";
  const storagePath = `customers/${customerId}/${documentType}/${crypto.randomUUID()}.${ext}`;

  const { error: uploadError } = await supabase.storage
    .from("kvota-documents")
    .upload(storagePath, file);
  if (uploadError) {
    if (
      uploadError.message?.includes("mime") ||
      uploadError.message?.includes("type")
    ) {
      throw new Error(
        `Формат файла "${ext}" не поддерживается. Допустимые: PDF, Word, Excel, JPG, PNG, WebP, ZIP`
      );
    }
    if (
      uploadError.message?.includes("size") ||
      uploadError.message?.includes("limit")
    ) {
      const sizeMb = Math.round(file.size / 1024 / 1024);
      throw new Error(`Файл слишком большой (${sizeMb} МБ). Максимум: 50 МБ`);
    }
    throw new Error(`Ошибка загрузки: ${uploadError.message}`);
  }

  const { data, error } = await supabase
    .from("documents")
    .insert({
      organization_id: organizationId,
      entity_type: "customer",
      entity_id: customerId,
      storage_path: storagePath,
      original_filename: file.name,
      file_size_bytes: file.size,
      mime_type: file.type || null,
      document_type: documentType,
      description: description?.trim() || null,
      uploaded_by: userId,
      status: "final",
    })
    .select(
      "id, storage_path, original_filename, file_size_bytes, mime_type, description, created_at"
    )
    .single();

  if (error) {
    // Clean up the orphaned storage object so we don't leak files when the
    // metadata insert fails (RLS, constraint, etc.).
    await supabase.storage.from("kvota-documents").remove([storagePath]);
    throw error;
  }
  return data as CustomerDocumentRow;
}

export async function deleteCustomerDocument(
  documentId: string,
  storagePath: string
) {
  const supabase = createClient();
  // Storage object first; the DB row holds the path so it must persist
  // until the file is gone, otherwise a re-render before delete completes
  // would show a broken link.
  const { error: storageError } = await supabase.storage
    .from("kvota-documents")
    .remove([storagePath]);
  if (storageError) {
    // Non-fatal: continue with metadata delete so the UI does not get stuck
    // showing rows whose underlying file is already missing on retry.
    console.warn(
      "[deleteCustomerDocument] storage remove failed:",
      storageError.message
    );
  }

  const { error } = await supabase
    .from("documents")
    .delete()
    .eq("id", documentId);
  if (error) throw error;
}

// ---------- Assignee mutations ----------

export async function addCustomerAssignee(
  customerId: string,
  userId: string
) {
  const supabase = createClient();
  const createdBy = await getCurrentUserId();
  const untyped = supabase as unknown as UntypedClient;

  const { error } = await untyped
    .from("customer_assignees")
    .insert({
      customer_id: customerId,
      user_id: userId,
      created_by: createdBy,
    });

  if (error) throw error;
}

export async function removeCustomerAssignee(
  customerId: string,
  userId: string
) {
  const supabase = createClient();
  const untyped = supabase as unknown as UntypedClient;

  const { error } = await untyped
    .from("customer_assignees")
    .delete()
    .eq("customer_id", customerId)
    .eq("user_id", userId);

  if (error) throw error;
}
