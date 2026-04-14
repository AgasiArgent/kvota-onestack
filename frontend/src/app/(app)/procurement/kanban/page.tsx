import { redirect } from "next/navigation";
import { getSessionUser, fetchProcurementWorkload } from "@/entities/user";
import { KanbanPage } from "@/features/procurement-kanban";
import { fetchKanbanData } from "@/features/procurement-kanban/api/server-queries";

export default async function ProcurementKanbanPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed =
    user.roles.includes("admin") ||
    user.roles.includes("head_of_procurement") ||
    user.roles.includes("procurement_senior") ||
    user.roles.includes("procurement");
  if (!isAllowed) redirect("/quotes");

  const orgId = user.orgId;
  const [data, workload] = await Promise.all([
    fetchKanbanData(),
    fetchProcurementWorkload(orgId),
  ]);

  return <KanbanPage data={data} workload={workload} orgId={orgId} />;
}
