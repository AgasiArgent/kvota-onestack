import { redirect } from "next/navigation";
import { fetchSuppliersList } from "@/entities/supplier/queries";
import { getSessionUser } from "@/entities/user";
import { hasProcurementAccess } from "@/shared/lib/roles";
import { SuppliersTable } from "@/features/suppliers";

interface Props {
  searchParams: Promise<{ q?: string; country?: string; status?: string; page?: string }>;
}

export default async function SuppliersPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  if (!hasProcurementAccess(user.roles)) redirect("/");

  const params = await searchParams;
  const search = params.q ?? "";
  const country = params.country ?? "";
  const status = params.status ?? "";
  const page = parseInt(params.page ?? "1", 10);

  const { data, total, activeCount, inactiveCount } = await fetchSuppliersList(
    user.orgId,
    { search, country, status, page },
    { id: user.id, roles: user.roles }
  );

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
        initialPage={page}
        orgId={user.orgId}
      />
    </div>
  );
}
