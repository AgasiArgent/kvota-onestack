import { createClient } from "@/shared/lib/supabase/client";
import type { BrandGroup } from "./types";

export async function upsertCalcSettings(
  orgId: string,
  data: {
    rate_forex_risk: number;
    rate_fin_comm: number;
    rate_loan_interest_daily: number;
  }
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("calculation_settings")
    .upsert(
      {
        organization_id: orgId,
        ...data,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "organization_id" }
    );

  if (error) throw error;
}

export async function upsertPhmbSettings(
  orgId: string,
  data: {
    base_price_per_pallet: number;
    logistics_price_per_pallet: number;
    customs_handling_cost: number;
    exchange_rate_insurance_pct: number;
    financial_transit_pct: number;
    customs_insurance_pct: number;
    default_markup_pct: number;
    default_advance_pct: number;
    default_payment_days: number;
    default_delivery_days: number;
  }
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("phmb_settings")
    .upsert(
      {
        org_id: orgId,
        ...data,
      },
      { onConflict: "org_id" }
    );

  if (error) throw error;
}

export async function updateBrandDiscount(id: string, discountPct: number) {
  const supabase = createClient();

  const { error } = await supabase
    .from("phmb_brand_type_discounts")
    .update({ discount_pct: discountPct, updated_at: new Date().toISOString() })
    .eq("id", id);

  if (error) throw error;
}

export async function deleteBrandDiscount(id: string) {
  const supabase = createClient();

  const { error } = await supabase
    .from("phmb_brand_type_discounts")
    .delete()
    .eq("id", id);

  if (error) throw error;
}

export async function createBrandGroup(
  orgId: string,
  name: string
): Promise<BrandGroup> {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("phmb_brand_groups")
    .insert({ org_id: orgId, name })
    .select("id, name")
    .single();

  if (error) throw error;

  return { id: data.id, name: data.name };
}

export async function deleteBrandGroup(id: string) {
  const supabase = createClient();

  const { error } = await supabase
    .from("phmb_brand_groups")
    .delete()
    .eq("id", id);

  if (error) throw error;
}
