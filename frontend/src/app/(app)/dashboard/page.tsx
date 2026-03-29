import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  DashboardContent,
  getPeriodRange,
  fetchQuotesMetrics,
  fetchProposalsMetrics,
  fetchDealsMetrics,
} from "@/features/dashboard";

const ALLOWED_ROLES = ["admin", "top_manager"];
const VALID_PERIODS = ["week", "month", "quarter", "year"];

interface Props {
  searchParams: Promise<{ period?: string }>;
}

export default async function DashboardPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const hasAccess = user.roles.some((r) => ALLOWED_ROLES.includes(r));
  if (!hasAccess) redirect("/quotes");

  const params = await searchParams;
  const period = VALID_PERIODS.includes(params.period ?? "")
    ? params.period!
    : "month";

  const range = getPeriodRange(period);

  const [quotes, proposals, deals] = await Promise.all([
    fetchQuotesMetrics(user.orgId, range),
    fetchProposalsMetrics(user.orgId, range),
    fetchDealsMetrics(user.orgId, range),
  ]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Дашборд</h1>
      <DashboardContent
        period={period}
        quotes={quotes}
        proposals={proposals}
        deals={deals}
      />
    </div>
  );
}
