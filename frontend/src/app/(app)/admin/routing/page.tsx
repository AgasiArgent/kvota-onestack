import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { RoutingPage } from "@/features/admin-routing";
import {
  fetchBrandsData,
  fetchGroupsData,
  fetchTenderData,
  fetchUnassignedData,
} from "@/features/admin-routing/api/server-queries";
import type { RoutingTab } from "@/features/admin-routing/model/types";

interface Props {
  searchParams: Promise<{ tab?: string }>;
}

const VALID_TABS: RoutingTab[] = ["brands", "groups", "tender", "unassigned"];

export default async function AdminRoutingPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed =
    user.roles.includes("admin") || user.roles.includes("head_of_procurement");
  if (!isAllowed) redirect("/quotes");

  const params = await searchParams;
  const rawTab = params.tab ?? "brands";
  const activeTab: RoutingTab = VALID_TABS.includes(rawTab as RoutingTab)
    ? (rawTab as RoutingTab)
    : "brands";

  const orgId = user.orgId;

  // Fetch only the active tab's data
  const brandsData =
    activeTab === "brands" ? await fetchBrandsData(orgId) : undefined;
  const groupsData =
    activeTab === "groups"
      ? { assignments: await fetchGroupsData(orgId) }
      : undefined;
  const tenderData =
    activeTab === "tender"
      ? { steps: await fetchTenderData(orgId) }
      : undefined;
  const unassignedData =
    activeTab === "unassigned"
      ? { items: await fetchUnassignedData(orgId) }
      : undefined;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Маршруты закупок</h1>
      <RoutingPage
        activeTab={activeTab}
        orgId={orgId}
        brandsData={brandsData}
        groupsData={groupsData}
        tenderData={tenderData}
        unassignedData={unassignedData}
      />
    </div>
  );
}
