import { redirect } from "next/navigation";
import { getSessionUser, fetchProcurementWorkload } from "@/entities/user/server";
import { DistributionPage } from "@/features/procurement-distribution";
import { fetchDistributionData } from "@/features/procurement-distribution/api/server-queries";

export default async function ProcurementDistributionPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement") ||
    user.roles.includes("procurement_senior");
  if (!isAllowed) redirect("/quotes");

  const orgId = user.orgId;

  const [quotes, workload] = await Promise.all([
    fetchDistributionData(orgId),
    fetchProcurementWorkload(orgId),
  ]);

  return (
    <DistributionPage quotes={quotes} workload={workload} orgId={orgId} />
  );
}
