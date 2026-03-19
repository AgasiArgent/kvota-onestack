"use client";

import { CompaniesTabs } from "./companies-tabs";
import { SellerTab } from "./seller-tab";
import { BuyerTab } from "./buyer-tab";
import type { CompanyTab, SellerCompany, BuyerCompany } from "../model/types";

interface Props {
  activeTab: CompanyTab;
  sellerCompanies?: SellerCompany[];
  buyerCompanies?: BuyerCompany[];
}

export function CompaniesPage({
  activeTab,
  sellerCompanies,
  buyerCompanies,
}: Props) {
  return (
    <CompaniesTabs activeTab={activeTab}>
      {activeTab === "seller" && sellerCompanies && (
        <SellerTab companies={sellerCompanies} />
      )}
      {activeTab === "buyer" && buyerCompanies && (
        <BuyerTab companies={buyerCompanies} />
      )}
    </CompaniesTabs>
  );
}
