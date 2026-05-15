import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  fetchKanbanInvoices,
  fetchTeamUsers,
  fetchWorkspaceStats,
} from "@/entities/workspace-invoice";
import { WorkspaceStatsStrip } from "@/features/workspace-logistics";
import { KanbanPage } from "@/features/workspace-kanban";
import {
  AnalyticsPanel,
  fetchWorkspaceAnalytics,
} from "@/features/workspace-analytics";

/**
 * /workspace/customs — customs kanban board (REQ-1).
 *
 * Three columns: Нераспределено / В работе / Завершено, derived from invoice
 * fields. Members see only their own «В работе» cards; heads see all and get
 * an assignee picker + stats/analytics strip.
 */
export default async function WorkspaceCustomsPage() {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");
  const orgId = user.orgId;

  // head_of_logistics ↔ head_of_customs are dual-hat (PR #105): either head
  // role grants full access in BOTH /workspace/logistics and /workspace/customs.
  const isHead =
    user.roles.includes("head_of_customs") ||
    user.roles.includes("head_of_logistics") ||
    user.roles.includes("admin") ||
    user.roles.includes("top_manager");

  const [board, teamUsers, stats, analyticsRows] = await Promise.all([
    fetchKanbanInvoices("customs", user.id, orgId, isHead),
    isHead ? fetchTeamUsers("customs", orgId) : Promise.resolve([]),
    isHead ? fetchWorkspaceStats("customs", orgId) : Promise.resolve(null),
    isHead ? fetchWorkspaceAnalytics("customs") : Promise.resolve([]),
  ]);

  return (
    <div className="space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-text">
          Таможня
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          {isHead ? "Управление очередью команды" : "Ваши заявки"}
        </p>
      </header>

      {isHead && stats && (
        <WorkspaceStatsStrip domain="customs" stats={stats} />
      )}

      <KanbanPage
        domain="customs"
        board={board}
        isHead={isHead}
        teamUsers={teamUsers}
      />

      {isHead && <AnalyticsPanel domain="customs" rows={analyticsRows} />}
    </div>
  );
}
