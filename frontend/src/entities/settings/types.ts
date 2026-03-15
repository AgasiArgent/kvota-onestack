export interface OrganizationInfo {
  id: string;
  name: string;
}

export interface CalcSettings {
  id: string;
  organization_id: string;
  rate_forex_risk: number;
  rate_fin_comm: number;
  rate_loan_interest_daily: number;
}

export interface PhmbSettings {
  id: string;
  org_id: string;
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

export interface BrandDiscount {
  id: string;
  org_id: string;
  brand: string;
  product_classification: string;
  discount_pct: number;
}

export interface BrandGroup {
  id: string;
  name: string;
}

export interface SettingsPageData {
  organization: OrganizationInfo;
  calcSettings: CalcSettings | null;
  phmbSettings: PhmbSettings | null;
  brandDiscounts: BrandDiscount[];
  brandGroups: BrandGroup[];
}
