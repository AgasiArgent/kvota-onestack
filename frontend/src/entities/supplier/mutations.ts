import { createClient } from "@/shared/lib/supabase/client";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedClient = { from: (table: string) => any };

function getUntypedClient(): UntypedClient {
  return createClient() as unknown as UntypedClient;
}

// ---------- Form data types ----------

export interface SupplierFormData {
  name: string;
  supplier_code?: string;
  country?: string;
  city?: string;
  registration_number?: string;
  default_payment_terms?: string;
}

export interface SupplierContactFormData {
  name: string;
  position?: string;
  email?: string;
  phone?: string;
  is_primary?: boolean;
  notes?: string;
}

// ---------- Helpers ----------

async function getSupplierOrgId(supplierId: string): Promise<string> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("suppliers")
    .select("organization_id")
    .eq("id", supplierId)
    .single();

  if (error || !data?.organization_id) {
    throw new Error("Failed to resolve organization for supplier");
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

// ---------- Supplier mutations ----------

export async function createSupplier(
  orgId: string,
  data: SupplierFormData
): Promise<{ id: string }> {
  const supabase = createClient();
  const userId = await getCurrentUserId();

  const { data: supplier, error } = await supabase
    .from("suppliers")
    .insert({
      name: data.name,
      supplier_code: data.supplier_code || null,
      country: data.country || null,
      city: data.city || null,
      default_payment_terms: data.default_payment_terms || null,
      organization_id: orgId,
      is_active: true,
      created_by: userId,
    })
    .select("id")
    .single();

  if (error) throw error;
  return supplier;
}

export async function updateSupplier(
  supplierId: string,
  data: Partial<SupplierFormData> & { is_active?: boolean }
) {
  const supabase = createClient();

  const updatePayload: Record<string, unknown> = {};
  if (data.name !== undefined) updatePayload.name = data.name;
  if (data.supplier_code !== undefined) updatePayload.supplier_code = data.supplier_code || null;
  if (data.country !== undefined) updatePayload.country = data.country || null;
  if (data.city !== undefined) updatePayload.city = data.city || null;
  if (data.default_payment_terms !== undefined) updatePayload.default_payment_terms = data.default_payment_terms || null;
  if (data.is_active !== undefined) updatePayload.is_active = data.is_active;

  const { error } = await supabase
    .from("suppliers")
    .update(updatePayload)
    .eq("id", supplierId);

  if (error) throw error;
}

// ---------- Contact mutations ----------

export async function createSupplierContact(
  supplierId: string,
  data: SupplierContactFormData
) {
  const untyped = getUntypedClient();
  const organizationId = await getSupplierOrgId(supplierId);
  const userId = await getCurrentUserId();

  const { data: contact, error } = await untyped
    .from("supplier_contacts")
    .insert({
      ...data,
      supplier_id: supplierId,
      organization_id: organizationId,
      created_by: userId,
    })
    .select()
    .single();

  if (error) throw error;
  return contact;
}

export async function updateSupplierContact(
  contactId: string,
  data: SupplierContactFormData
) {
  const untyped = getUntypedClient();

  const { data: contact, error } = await untyped
    .from("supplier_contacts")
    .update(data)
    .eq("id", contactId)
    .select()
    .single();

  if (error) throw error;
  return contact;
}

export async function deleteSupplierContact(contactId: string) {
  const untyped = getUntypedClient();

  const { error } = await untyped
    .from("supplier_contacts")
    .delete()
    .eq("id", contactId);

  if (error) throw error;
}

// ---------- Brand assignment mutations ----------

export async function addBrandAssignment(
  supplierId: string,
  data: { brand: string; is_primary?: boolean; notes?: string }
) {
  const supabase = createClient();
  const [organizationId, userId] = await Promise.all([
    getSupplierOrgId(supplierId),
    getCurrentUserId(),
  ]);

  const { data: assignment, error } = await supabase
    .from("brand_supplier_assignments")
    .insert({
      brand: data.brand,
      supplier_id: supplierId,
      organization_id: organizationId,
      is_primary: data.is_primary ?? false,
      notes: data.notes || null,
      created_by: userId,
    })
    .select()
    .single();

  if (error) throw error;
  return assignment;
}

export async function deleteBrandAssignment(assignmentId: string) {
  const supabase = createClient();

  const { error } = await supabase
    .from("brand_supplier_assignments")
    .delete()
    .eq("id", assignmentId);

  if (error) throw error;
}

export async function toggleBrandPrimary(
  assignmentId: string,
  isPrimary: boolean
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("brand_supplier_assignments")
    .update({ is_primary: isPrimary })
    .eq("id", assignmentId);

  if (error) throw error;
}
