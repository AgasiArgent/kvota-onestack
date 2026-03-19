export interface SellerCompany {
  id: string;
  name: string;
  supplier_code: string;
  country: string | null;
  inn: string | null;
  kpp: string | null;
  is_active: boolean | null;
}

export interface BuyerCompany {
  id: string;
  name: string;
  company_code: string;
  country: string | null;
  inn: string | null;
  kpp: string | null;
  is_active: boolean | null;
}

export type CompanyTab = "seller" | "buyer";
