import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { RoutingPage } from "@/features/admin-routing";
import {
  fetchBrandsData,
  fetchGroupsData,
  fetchTenderData,
  fetchUnassignedData,
  fetchLogisticsTemplatesForAdmin,
} from "@/features/admin-routing/api/server-queries";
import type { RoutingTab } from "@/features/admin-routing/model/types";

interface Props {
  searchParams: Promise<{ tab?: string }>;
}

const VALID_TABS: RoutingTab[] = [
  "brands",
  "groups",
  "tender",
  "unassigned",
  "logistics",
];

// Roles that may see the logistics-templates tab. Admins see everything;
// head_of_logistics owns the templates; logistics can create per spec §3.13.
const LOGISTICS_TAB_ROLES = new Set([
  "admin",
  "head_of_logistics",
  "logistics",
]);

export default async function AdminRoutingPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const canManageProcurement =
    user.roles.includes("admin") || user.roles.includes("head_of_procurement");
  const canManageLogistics = user.roles.some((r) =>
    LOGISTICS_TAB_ROLES.has(r),
  );
  if (!canManageProcurement && !canManageLogistics) redirect("/quotes");

  const params = await searchParams;
  const rawTab = params.tab ?? (canManageProcurement ? "brands" : "logistics");
  const activeTab: RoutingTab = VALID_TABS.includes(rawTab as RoutingTab)
    ? (rawTab as RoutingTab)
    : "brands";

  // Non-procurement users should not peek into procurement-only tabs.
  if (!canManageProcurement && activeTab !== "logistics") {
    redirect("/admin/routing?tab=logistics");
  }

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
  const logisticsData =
    activeTab === "logistics"
      ? { templates: await fetchLogisticsTemplatesForAdmin(orgId) }
      : undefined;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Маршруты закупок и логистики</h1>
      <RoutingPage
        activeTab={activeTab}
        orgId={orgId}
        brandsData={brandsData}
        groupsData={groupsData}
        tenderData={tenderData}
        unassignedData={unassignedData}
        logisticsData={logisticsData}
      />
    </div>
  );
}
