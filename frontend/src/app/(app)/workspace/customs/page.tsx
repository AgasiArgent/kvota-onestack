import { redirect, notFound } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  fetchMyAssignedInvoices,
  fetchMyCompletedInvoices,
  fetchUnassignedInvoices,
  fetchAllActiveInvoices,
  fetchTeamUsers,
  fetchWorkspaceStats,
} from "@/entities/workspace-invoice";
import { WorkspaceInvoicesTable } from "@/features/workspace-logistics/ui/workspace-invoices-table";
import { WorkspaceStatsStrip } from "@/features/workspace-logistics/ui/workspace-stats-strip";
import { UnassignedInbox } from "@/features/workspace-logistics/ui/unassigned-inbox";
import { WorkspaceLogisticsClient } from "../logistics/workspace-logistics-client";

type Tab = "my" | "completed" | "unassigned" | "all";

interface PageProps {
  searchParams: Promise<{ tab?: string }>;
}

export default async function WorkspaceCustomsPage({ searchParams }: PageProps) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");
  const orgId = user.orgId;

  const isHead =
    user.roles.includes("head_of_customs") ||
    user.roles.includes("admin") ||
    user.roles.includes("top_manager");

  const { tab } = await searchParams;
  const activeTab: Tab =
    (["my", "completed", "unassigned", "all"] as const).find((t) => t === tab) ?? "my";

  if (!isHead && (activeTab === "unassigned" || activeTab === "all")) notFound();

  const [my, completed, unassigned, all, teamUsers, stats] = await Promise.all([
    fetchMyAssignedInvoices("customs", user.id, orgId),
    fetchMyCompletedInvoices("customs", user.id, orgId),
    isHead ? fetchUnassignedInvoices("customs", orgId) : Promise.resolve([]),
    isHead ? fetchAllActiveInvoices("customs", orgId) : Promise.resolve([]),
    isHead ? fetchTeamUsers("customs", orgId) : Promise.resolve([]),
    isHead ? fetchWorkspaceStats("customs", orgId) : Promise.resolve(null),
  ]);

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      <header>
        <h1 className="text-2xl font-semibold text-text tracking-tight">Таможня</h1>
        <p className="text-sm text-text-muted mt-1">
          {isHead ? "Управление очередью команды" : "Ваши заявки"}
        </p>
      </header>

      {isHead && stats && <WorkspaceStatsStrip domain="customs" stats={stats} />}

      <WorkspaceLogisticsClient
        domain="customs"
        userRoles={user.roles}
        activeTab={activeTab}
        counts={{ my: my.length, completed: completed.length, unassigned: unassigned.length, all: all.length }}
      >
        {{
          my: <WorkspaceInvoicesTable domain="customs" viewKind="my" invoices={my} emptyLabel="Свободен — заявок в работе нет" />,
          completed: <WorkspaceInvoicesTable domain="customs" viewKind="completed" invoices={completed} emptyLabel="Завершённых заявок ещё нет" />,
          unassigned: <UnassignedInbox domain="customs" invoices={unassigned} teamUsers={teamUsers} />,
          all: <WorkspaceInvoicesTable domain="customs" viewKind="all" invoices={all} emptyLabel="Нет заявок" />,
        }}
      </WorkspaceLogisticsClient>
    </div>
  );
}
