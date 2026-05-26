"use client";

import { CompaniesTabs } from "./companies-tabs";
import { SellerTab } from "./seller-tab";
import { BuyerTab } from "./buyer-tab";
import type { CompanyTab, SellerCompany, BuyerCompany } from "../model/types";

interface Props {
  activeTab: CompanyTab;
  sellerCompanies?: SellerCompany[];
  buyerCompanies?: BuyerCompany[];
  /** Org of the current viewer — required by the buyer create dialog. */
  orgId: string;
  /**
   * Whether the viewer may create / edit buyer companies. Gated by
   * `canManageBuyerCompany(roles)` server-side and aligned with the
   * widened buyer_companies RLS policy (migration 331).
   */
  canManageBuyer?: boolean;
}

export function CompaniesPage({
  activeTab,
  sellerCompanies,
  buyerCompanies,
  orgId,
  canManageBuyer = false,
}: Props) {
  return (
    <CompaniesTabs activeTab={activeTab}>
      {activeTab === "seller" && sellerCompanies && (
        <SellerTab companies={sellerCompanies} />
      )}
      {activeTab === "buyer" && buyerCompanies && (
        <BuyerTab
          companies={buyerCompanies}
          orgId={orgId}
          canManage={canManageBuyer}
        />
      )}
    </CompaniesTabs>
  );
}
