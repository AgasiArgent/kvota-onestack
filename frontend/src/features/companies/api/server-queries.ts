import { createAdminClient } from "@/shared/lib/supabase/server";
import type { SellerCompany, BuyerCompany } from "../model/types";

export async function fetchSellerCompanies(
  orgId: string
): Promise<SellerCompany[]> {
  const supabase = createAdminClient();

  const { data, error } = await supabase
    .from("seller_companies")
    .select("id, name, supplier_code, country, inn, kpp, is_active")
    .eq("organization_id", orgId)
    .order("name");

  if (error) throw error;

  return data ?? [];
}

export async function fetchBuyerCompanies(
  orgId: string
): Promise<BuyerCompany[]> {
  const supabase = createAdminClient();

  const { data, error } = await supabase
    .from("buyer_companies")
    .select("id, name, company_code, country, inn, kpp, is_active")
    .eq("organization_id", orgId)
    .order("name");

  if (error) throw error;

  return data ?? [];
}
