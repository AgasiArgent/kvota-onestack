"use client";

import { createClient } from "@/shared/lib/supabase/client";

export interface BuyerCompanyFormData {
  name: string;
  company_code: string;
  country?: string | null;
  inn?: string | null;
  kpp?: string | null;
  ogrn?: string | null;
  registration_address?: string | null;
  general_director_name?: string | null;
  general_director_position?: string | null;
  is_active?: boolean;
}

/**
 * Insert a new buyer company. RLS gates the write to admin / finance /
 * procurement tier (migration 331). The server enforces — this function only
 * surfaces errors back to the caller.
 */
export async function createBuyerCompany(
  orgId: string,
  data: BuyerCompanyFormData
): Promise<{ id: string }> {
  const supabase = createClient();
  const { data: row, error } = await supabase
    .from("buyer_companies")
    .insert({
      organization_id: orgId,
      name: data.name,
      company_code: data.company_code,
      country: data.country ?? null,
      inn: data.inn ?? null,
      kpp: data.kpp ?? null,
      ogrn: data.ogrn ?? null,
      registration_address: data.registration_address ?? null,
      general_director_name: data.general_director_name ?? null,
      general_director_position: data.general_director_position ?? null,
      is_active: data.is_active ?? true,
    })
    .select("id")
    .single();
  if (error) throw error;
  return { id: row.id };
}

/**
 * Update an existing buyer company. Only fields present on `data` are written
 * — undefined fields are left untouched on the server-side row.
 */
export async function updateBuyerCompany(
  id: string,
  data: Partial<BuyerCompanyFormData>
): Promise<void> {
  const supabase = createClient();
  // Strip undefined so the partial update doesn't blank out columns the
  // caller omitted from `data`.
  const patch: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(data)) {
    if (value !== undefined) patch[key] = value;
  }
  const { error } = await supabase
    .from("buyer_companies")
    .update(patch)
    .eq("id", id);
  if (error) throw error;
}
