import { redirect } from "next/navigation";
import { fetchCustomersList, fetchCustomerFinancials } from "@/entities/customer";
import { getSessionUser, fetchUserSalesGroupId } from "@/entities/user/server";
import { isSalesOnly } from "@/shared/lib/roles";
import { CustomersTable } from "@/features/customers";

interface Props {
  searchParams: Promise<{ q?: string; status?: string; page?: string }>;
}

export default async function CustomersPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const params = await searchParams;
  const search = params.q ?? "";
  const status = params.status ?? "";
  const page = parseInt(params.page ?? "1", 10);

  // Fetch salesGroupId only for sales-only users (avoids unnecessary query for others)
  const salesGroupId = isSalesOnly(user.roles)
    ? await fetchUserSalesGroupId(user.id, user.orgId)
    : null;

  const [{ data, total }, financials] = await Promise.all([
    fetchCustomersList(
      { search, status, page },
      { id: user.id, roles: user.roles, salesGroupId, orgId: user.orgId }
    ),
    fetchCustomerFinancials(user.orgId),
  ]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Клиенты</h1>
      <CustomersTable
        initialData={data}
        initialTotal={total}
        initialSearch={search}
        initialStatus={status}
        initialPage={page}
        orgId={user.orgId}
        financials={financials}
      />
    </div>
  );
}
