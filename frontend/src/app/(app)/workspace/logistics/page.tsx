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
import {
  AnalyticsPanel,
  fetchWorkspaceAnalytics,
} from "@/features/workspace-analytics";
import { WorkspaceLogisticsClient } from "./workspace-logistics-client";

type Tab = "my" | "completed" | "unassigned" | "all";

interface PageProps {
  searchParams: Promise<{ tab?: string }>;
}

export default async function WorkspaceLogisticsPage({ searchParams }: PageProps) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");
  const orgId = user.orgId;

  // head_of_logistics ↔ head_of_customs are dual-hat (PR #105): either head
  // role grants full access in BOTH /workspace/logistics and /workspace/customs.
  const isHead =
    user.roles.includes("head_of_logistics") ||
    user.roles.includes("head_of_customs") ||
    user.roles.includes("admin") ||
    user.roles.includes("top_manager");

  const { tab } = await searchParams;
  // Heads (head_of_logistics / head_of_customs / admin / top_manager) manage
  // the team queue, so their landing tab is «Все заявки» — mirrors the
  // sales-style scope where head_of_sales lands on the org-wide list, not
  // their personal one (L-D 1.1).
  const defaultTab: Tab = isHead ? "all" : "my";
  const activeTab: Tab =
    (["my", "completed", "unassigned", "all"] as const).find((t) => t === tab) ?? defaultTab;

  if (!isHead && (activeTab === "unassigned" || activeTab === "all")) notFound();

  const [my, completed, unassigned, all, teamUsers, stats, analyticsRows] =
    await Promise.all([
      fetchMyAssignedInvoices("logistics", user.id, orgId),
      fetchMyCompletedInvoices("logistics", user.id, orgId),
      isHead ? fetchUnassignedInvoices("logistics", orgId) : Promise.resolve([]),
      isHead ? fetchAllActiveInvoices("logistics", orgId) : Promise.resolve([]),
      isHead ? fetchTeamUsers("logistics", orgId) : Promise.resolve([]),
      isHead ? fetchWorkspaceStats("logistics", orgId) : Promise.resolve(null),
      isHead ? fetchWorkspaceAnalytics("logistics") : Promise.resolve([]),
    ]);

  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-text tracking-tight">Логистика</h1>
        <p className="text-sm text-text-muted mt-1">
          {isHead ? "Управление очередью команды" : "Ваши заявки"}
        </p>
      </header>

      {isHead && stats && <WorkspaceStatsStrip domain="logistics" stats={stats} />}

      <WorkspaceLogisticsClient
        userRoles={user.roles}
        activeTab={activeTab}
        defaultTab={defaultTab}
        counts={{ my: my.length, completed: completed.length, unassigned: unassigned.length, all: all.length }}
      >
        {{
          my: <WorkspaceInvoicesTable domain="logistics" viewKind="my" invoices={my} emptyLabel="Свободен — заявок в работе нет" />,
          completed: <WorkspaceInvoicesTable domain="logistics" viewKind="completed" invoices={completed} emptyLabel="Завершённых заявок ещё нет" />,
          unassigned: <UnassignedInbox domain="logistics" invoices={unassigned} teamUsers={teamUsers} />,
          all: <WorkspaceInvoicesTable domain="logistics" viewKind="all" invoices={all} emptyLabel="Нет заявок" />,
        }}
      </WorkspaceLogisticsClient>

      {isHead && <AnalyticsPanel domain="logistics" rows={analyticsRows} />}
    </div>
  );
}
