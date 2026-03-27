import { createAdminClient } from "@/shared/lib/supabase/server";
import { escapePostgrestFilter } from "@/shared/lib/supabase/escape-filter";
import type {
  SupplierListItem,
  SupplierDetail,
  SupplierContact,
  BrandAssignment,
} from "./types";

const PAGE_SIZE = 50;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type UntypedClient = { from: (table: string) => any };

/**
 * supplier_contacts table is not in generated DB types yet (migration 217).
 * Use untyped client for queries to that table.
 */
function getUntypedClient(): UntypedClient {
  return createAdminClient() as unknown as UntypedClient;
}

interface ContactRow {
  supplier_id: string;
  name: string;
  email: string | null;
}

async function fetchPrimaryContactsForSuppliers(
  supplierIds: string[]
): Promise<ContactRow[]> {
  if (supplierIds.length === 0) return [];
  const untyped = getUntypedClient();
  const { data } = await untyped
    .from("supplier_contacts")
    .select("supplier_id, name, email")
    .in("supplier_id", supplierIds)
    .eq("is_primary", true);
  return (data ?? []) as ContactRow[];
}

export async function fetchSuppliersList(
  orgId: string,
  params: {
    search?: string;
    country?: string;
    status?: string;
    page?: number;
  }
): Promise<{ data: SupplierListItem[]; total: number; activeCount: number; inactiveCount: number }> {
  const supabase = createAdminClient();
  const { search = "", country = "", status = "", page = 1 } = params;
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let query = supabase
    .from("suppliers")
    .select("id, name, supplier_code, country, city, is_active", {
      count: "exact",
    })
    .eq("organization_id", orgId)
    .order("name")
    .range(from, to);

  if (search) {
    const escaped = escapePostgrestFilter(search);
    query = query.or(`name.ilike.%${escaped}%,supplier_code.ilike.%${escaped}%`);
  }
  if (country) {
    query = query.eq("country", country);
  }
  if (status === "active") query = query.eq("is_active", true);
  if (status === "inactive") query = query.eq("is_active", false);

  const { data, count, error } = await query;
  if (error) throw error;

  const rows = data ?? [];
  const supplierIds = rows.map((s) => s.id);

  // Fetch primary contacts and active/inactive counts in parallel
  const [contactsResult, allStatuses] = await Promise.all([
    fetchPrimaryContactsForSuppliers(supplierIds),
    supabase
      .from("suppliers")
      .select("is_active")
      .eq("organization_id", orgId),
  ]);

  const contactMap = new Map(
    contactsResult.map((c: ContactRow) => [c.supplier_id, { name: c.name, email: c.email }])
  );

  const allList = allStatuses.data ?? [];
  const activeCount = allList.filter((s) => s.is_active !== false).length;
  const inactiveCount = allList.filter((s) => s.is_active === false).length;

  const items: SupplierListItem[] = rows.map((row) => {
    const contact = contactMap.get(row.id);
    return {
      id: row.id,
      name: row.name,
      supplier_code: row.supplier_code,
      country: row.country,
      city: row.city,
      registration_number: null,
      is_active: row.is_active !== false,
      primary_contact_name: contact?.name ?? null,
      primary_contact_email: contact?.email ?? null,
    };
  });

  return { data: items, total: count ?? 0, activeCount, inactiveCount };
}

export async function fetchSupplierDetail(
  id: string
): Promise<SupplierDetail | null> {
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("suppliers")
    .select("*")
    .eq("id", id)
    .single();
  if (error) return null;

  return {
    id: data.id,
    organization_id: data.organization_id,
    name: data.name,
    supplier_code: data.supplier_code,
    country: data.country,
    city: data.city,
    // registration_number added in migration 217, not yet in generated types
    registration_number: (data as unknown as Record<string, unknown>).registration_number as string | null ?? null,
    default_payment_terms: data.default_payment_terms,
    is_active: data.is_active !== false,
    created_at: data.created_at ?? "",
    updated_at: data.updated_at,
  } as SupplierDetail;
}

export async function fetchSupplierContacts(
  supplierId: string
): Promise<SupplierContact[]> {
  const untyped = getUntypedClient();
  const { data, error } = await untyped
    .from("supplier_contacts")
    .select("*")
    .eq("supplier_id", supplierId)
    .order("is_primary", { ascending: false })
    .order("name");
  if (error) throw error;
  return (data ?? []) as SupplierContact[];
}

export async function fetchBrandAssignments(
  supplierId: string
): Promise<BrandAssignment[]> {
  const supabase = createAdminClient();
  const { data, error } = await supabase
    .from("brand_supplier_assignments")
    .select("id, brand, supplier_id, is_primary, notes, created_at")
    .eq("supplier_id", supplierId)
    .order("brand");
  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    brand: row.brand,
    supplier_id: row.supplier_id,
    is_primary: row.is_primary ?? false,
    notes: row.notes,
    created_at: row.created_at,
  }));
}
