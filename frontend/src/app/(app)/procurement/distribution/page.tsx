import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { DistributionPage } from "@/features/procurement-distribution";
import {
  fetchDistributionData,
  fetchProcurementWorkload,
} from "@/features/procurement-distribution/api/server-queries";

export default async function ProcurementDistributionPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement");
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
