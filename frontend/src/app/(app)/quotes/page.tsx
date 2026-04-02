import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { fetchQuotesList, fetchFilterOptions, getActionStatusesForUser } from "@/entities/quote";
import type { QuotesFilterParams } from "@/entities/quote";
import { QuotesTable } from "@/features/quotes";

interface Props {
  searchParams: Promise<{
    status?: string;
    customer?: string;
    manager?: string;
    search?: string;
    page?: string;
  }>;
}

export default async function QuotesPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const params = await searchParams;

  const filters: QuotesFilterParams = {
    status: params.status || undefined,
    customer: params.customer && params.customer !== "all" ? params.customer : undefined,
    manager: params.manager && params.manager !== "all" ? params.manager : undefined,
    search: params.search || undefined,
    page: params.page ? parseInt(params.page, 10) : 1,
  };

  const [quotesResult, filterOptions] = await Promise.all([
    fetchQuotesList(filters, {
      id: user.id,
      roles: user.roles,
      org_id: user.orgId,
    }),
    fetchFilterOptions(user.orgId, { id: user.id, roles: user.roles }),
  ]);

  const actionStatuses = new Set(getActionStatusesForUser(user.roles));
  const actionQuotes = quotesResult.data.filter((q) =>
    actionStatuses.has(q.workflow_status)
  );
  const otherQuotes = quotesResult.data.filter(
    (q) => !actionStatuses.has(q.workflow_status)
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Коммерческие предложения</h1>
      <QuotesTable
        actionQuotes={actionQuotes}
        otherQuotes={otherQuotes}
        total={quotesResult.total}
        page={quotesResult.page}
        pageSize={quotesResult.pageSize}
        filters={filters}
        customers={filterOptions.customers}
        managers={filterOptions.managers}
        userRoles={user.roles}
        userId={user.id}
        orgId={user.orgId}
      />
    </div>
  );
}
