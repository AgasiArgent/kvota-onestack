import { createClient } from "@/shared/lib/supabase/server";
import type {
  SettingsPageData,
  CalcSettings,
  PhmbSettings,
  BrandDiscount,
  BrandGroup,
} from "./types";

export async function fetchSettingsPageData(
  orgId: string
): Promise<SettingsPageData> {
  const supabase = await createClient();

  const [orgResult, calcResult, phmbResult, discountsResult, groupsResult] =
    await Promise.all([
      supabase
        .from("organizations")
        .select("id, name")
        .eq("id", orgId)
        .single(),
      supabase
        .from("calculation_settings")
        .select("id, organization_id, rate_forex_risk, rate_fin_comm, rate_loan_interest_daily")
        .eq("organization_id", orgId)
        .maybeSingle(),
      supabase
        .from("phmb_settings")
        .select(
          "id, org_id, base_price_per_pallet, logistics_price_per_pallet, customs_handling_cost, exchange_rate_insurance_pct, financial_transit_pct, customs_insurance_pct, default_markup_pct, default_advance_pct, default_payment_days, default_delivery_days"
        )
        .eq("org_id", orgId)
        .maybeSingle(),
      supabase
        .from("phmb_brand_type_discounts")
        .select("id, org_id, brand, product_classification, discount_pct")
        .eq("org_id", orgId)
        .order("brand"),
      supabase
        .from("phmb_brand_groups")
        .select("id, name")
        .eq("org_id", orgId)
        .order("sort_order"),
    ]);

  if (orgResult.error || !orgResult.data) {
    throw new Error(`Failed to load organization: ${orgResult.error?.message ?? 'not found'}`);
  }
  const organization = orgResult.data;

  return {
    organization,
    calcSettings: (calcResult.data as CalcSettings) ?? null,
    phmbSettings: (phmbResult.data as PhmbSettings) ?? null,
    brandDiscounts: (discountsResult.data ?? []) as BrandDiscount[],
    brandGroups: (groupsResult.data ?? []) as BrandGroup[],
  };
}
