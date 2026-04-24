import { notFound, redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user/server";
import {
  CostAnalysisView,
  COST_ANALYSIS_ROLES,
  fetchCostAnalysis,
} from "@/features/cost-analysis";

interface Props {
  params: Promise<{ id: string }>;
}

/**
 * Cost Analysis page — read-only P&L waterfall for a quote.
 * Visible to finance, top_manager, admin, quote_controller only.
 *
 * - Role gate: performed client-side via getSessionUser() roles (fast path)
 *   AND server-side via the FastAPI endpoint (authoritative).
 * - Auth gate: falls back to /login when the session is missing.
 * - 404 when the quote is missing, deleted, or in a different org.
 */
export default async function QuoteCostAnalysisPage({ params }: Props) {
  const { id } = await params;

  const user = await getSessionUser();
  if (!user?.id) redirect("/login");

  const allowedRoles = new Set<string>(COST_ANALYSIS_ROLES);
  const hasAllowedRole = user.roles.some((role) => allowedRoles.has(role));
  if (!hasAllowedRole) redirect("/");

  const response = await fetchCostAnalysis(id);

  if (!response.success || !response.data) {
    const code = response.error?.code ?? "UNKNOWN";
    if (code === "NOT_FOUND") notFound();
    if (code === "FORBIDDEN") redirect("/");
    if (code === "UNAUTHORIZED") redirect("/login");
    // Fall through — render a minimal error screen so the user isn't left blank.
    return (
      <div className="p-6 text-sm text-destructive">
        Не удалось загрузить кост-анализ: {response.error?.message ?? "unknown error"}
      </div>
    );
  }

  return <CostAnalysisView data={response.data} />;
}
