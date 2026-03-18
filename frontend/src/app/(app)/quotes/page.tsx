import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { fetchQuotesList, fetchFilterOptions } from "@/entities/quote";
import type { QuotesFilterParams } from "@/entities/quote";
import { QuotesTable } from "@/features/quotes";

interface Props {
  searchParams: Promise<{
    status?: string;
    customer?: string;
    manager?: string;
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

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Коммерческие предложения</h1>
      <QuotesTable
        quotes={quotesResult.data}
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
