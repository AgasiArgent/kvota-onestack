import { fetchCustomersList } from "@/entities/customer";
import { CustomersTable } from "@/features/customers";

interface Props {
  searchParams: Promise<{ q?: string; status?: string; page?: string }>;
}

export default async function CustomersPage({ searchParams }: Props) {
  const params = await searchParams;
  const search = params.q ?? "";
  const status = params.status ?? "";
  const page = parseInt(params.page ?? "1", 10);

  const { data, total } = await fetchCustomersList({ search, status, page });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Клиенты</h1>
      <CustomersTable
        initialData={data}
        initialTotal={total}
        initialSearch={search}
        initialStatus={status}
        initialPage={page}
      />
    </div>
  );
}
