import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  fetchCurrencyInvoices,
  canAccessCurrencyInvoices,
} from "@/entities/currency-invoice";
import type { CIFilterParams } from "@/entities/currency-invoice";
import { CITable } from "@/features/currency-invoices";

interface Props {
  searchParams: Promise<{
    status?: string;
    segment?: string;
    page?: string;
  }>;
}

export default async function CurrencyInvoicesPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  if (!canAccessCurrencyInvoices(user.roles)) {
    redirect("/quotes");
  }

  const params = await searchParams;

  const filters: CIFilterParams = {
    status: params.status || undefined,
    segment: params.segment || undefined,
    page: params.page ? parseInt(params.page, 10) : 1,
  };

  const result = await fetchCurrencyInvoices(user.orgId, filters);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Валютные инвойсы</h1>
      <CITable
        invoices={result.data}
        total={result.total}
        page={result.page}
        pageSize={result.pageSize}
        filters={filters}
      />
    </div>
  );
}
