import { redirect } from "next/navigation";
import { fetchSuppliersList } from "@/entities/supplier/queries";
import { getSessionUser } from "@/entities/user";
import { SuppliersTable } from "@/features/suppliers/ui/suppliers-table";

interface Props {
  searchParams: Promise<{ q?: string; country?: string; status?: string; page?: string }>;
}

export default async function SuppliersPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed =
    user.roles.includes("admin") || user.roles.includes("procurement") || user.roles.includes("procurement_senior");
  if (!isAllowed) redirect("/");

  const params = await searchParams;
  const search = params.q ?? "";
  const country = params.country ?? "";
  const status = params.status ?? "";
  const page = parseInt(params.page ?? "1", 10);

  const { data, total, activeCount, inactiveCount } = await fetchSuppliersList(
    user.orgId,
    { search, country, status, page }
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
