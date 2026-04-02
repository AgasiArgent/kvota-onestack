import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { CompaniesPage } from "@/features/companies";
import {
  fetchSellerCompanies,
  fetchBuyerCompanies,
} from "@/features/companies/api/server-queries";
import type { CompanyTab } from "@/features/companies/model/types";

interface Props {
  searchParams: Promise<{ tab?: string }>;
}

const VALID_TABS: CompanyTab[] = ["seller", "buyer"];
const ALLOWED_ROLES = ["admin", "finance", "procurement", "procurement_senior"];

export default async function CompaniesPageRoute({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed = ALLOWED_ROLES.some((role) => user.roles.includes(role));
  if (!isAllowed) redirect("/");

  const params = await searchParams;
  const rawTab = params.tab ?? "seller";
  const activeTab: CompanyTab = VALID_TABS.includes(rawTab as CompanyTab)
    ? (rawTab as CompanyTab)
    : "seller";

  const orgId = user.orgId;

  const sellerCompanies =
    activeTab === "seller" ? await fetchSellerCompanies(orgId) : undefined;
  const buyerCompanies =
    activeTab === "buyer" ? await fetchBuyerCompanies(orgId) : undefined;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Юрлица</h1>
      <CompaniesPage
        activeTab={activeTab}
        sellerCompanies={sellerCompanies}
        buyerCompanies={buyerCompanies}
      />
    </div>
  );
}
