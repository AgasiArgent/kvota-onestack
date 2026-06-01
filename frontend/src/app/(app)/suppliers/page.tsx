import { redirect } from "next/navigation";
import {
  fetchSuppliersList,
  fetchSupplierFilterOptions,
} from "@/entities/supplier";
import { getSessionUser } from "@/entities/user";
import { hasProcurementAccess } from "@/shared/lib/roles";
import { SuppliersTable } from "@/features/suppliers";

interface Props {
  searchParams: Promise<{
    q?: string;
    country?: string;
    status?: string;
    assignee?: string;
    brand?: string;
    page?: string;
  }>;
}

export default async function SuppliersPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  if (!hasProcurementAccess(user.roles)) redirect("/");

  const params = await searchParams;
  const search = params.q ?? "";
  const country = params.country ?? "";
  const status = params.status ?? "";
  const assignee = params.assignee ?? "";
  const brand = params.brand ?? "";
  const page = parseInt(params.page ?? "1", 10);

  const accessUser = { id: user.id, roles: user.roles };

  // List + filter options are independent — fetch in parallel (no waterfall).
  const [{ data, total, activeCount, inactiveCount }, filterOptions] =
    await Promise.all([
      fetchSuppliersList(
        user.orgId,
        { search, country, status, assignee, brand, page },
        accessUser
      ),
      fetchSupplierFilterOptions(user.orgId, accessUser),
    ]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Поставщики</h1>
      <SuppliersTable
        initialData={data}
        initialTotal={total}
        activeCount={activeCount}
        inactiveCount={inactiveCount}
        initialSearch={search}
        initialCountry={country}
        initialStatus={status}
        initialAssignee={assignee}
        initialBrand={brand}
        initialPage={page}
        filterOptions={filterOptions}
        orgId={user.orgId}
      />
    </div>
  );
}
