import Link from "next/link";
import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { canAccessFinance } from "@/entities/finance/types";
import { fetchDeals, fetchPayments, fetchSupplierInvoices } from "@/entities/finance/queries";
import type { DealsFilterParams, PaymentsFilterParams, SupplierInvoicesFilterParams } from "@/entities/finance/types";
import { DealsTab } from "@/features/finance/ui/deals-tab";
import { PaymentsTab } from "@/features/finance/ui/payments-tab";
import { SupplierInvoicesTab } from "@/features/finance/ui/supplier-invoices-tab";

type TabKey = "deals" | "payments" | "invoices";

const TABS: { key: TabKey; label: string }[] = [
  { key: "deals", label: "Сделки" },
  { key: "payments", label: "Платежи" },
  { key: "invoices", label: "Инвойсы поставщиков" },
];

interface Props {
  searchParams: Promise<{
    tab?: string;
    status?: string;
    page?: string;
    // Payments filters
    grouping?: string;
    type?: string;
    payment_status?: string;
    date_from?: string;
    date_to?: string;
  }>;
}

export default async function FinancePage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");
  if (!canAccessFinance(user.roles)) redirect("/quotes");

  const params = await searchParams;
  const activeTab = (
    TABS.some((t) => t.key === params.tab) ? params.tab : "deals"
  ) as TabKey;
  const currentPage = params.page ? parseInt(params.page, 10) : 1;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Финансы</h1>

      {/* Tab navigation */}
      <div className="flex gap-1 mb-6 border-b">
        {TABS.map((tab) => (
          <Link
            key={tab.key}
            href={`/finance?tab=${tab.key}`}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? "border-accent text-accent"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted"
            }`}
          >
            {tab.label}
          </Link>
        ))}
      </div>

      {/* Active tab content */}
      {activeTab === "deals" && (
        <DealsTabLoader orgId={user.orgId} page={currentPage} status={params.status} />
      )}
      {activeTab === "payments" && (
        <PaymentsTabLoader
          orgId={user.orgId}
          page={currentPage}
          type={params.type}
          paymentStatus={params.payment_status}
          dateFrom={params.date_from}
          dateTo={params.date_to}
        />
      )}
      {activeTab === "invoices" && (
        <InvoicesTabLoader orgId={user.orgId} page={currentPage} />
      )}
    </div>
  );
}

async function DealsTabLoader({
  orgId,
  page,
  status,
}: {
  orgId: string;
  page: number;
  status?: string;
}) {
  const filters: DealsFilterParams = {
    status: status || undefined,
    page,
  };

  const result = await fetchDeals(orgId, filters);

  return (
    <DealsTab
      deals={result.data}
      summary={result.summary}
      total={result.total}
      page={result.page}
      pageSize={result.pageSize}
      filters={filters}
    />
  );
}

async function PaymentsTabLoader({
  orgId,
  page,
  type,
  paymentStatus,
  dateFrom,
  dateTo,
}: {
  orgId: string;
  page: number;
  type?: string;
  paymentStatus?: string;
  dateFrom?: string;
  dateTo?: string;
}) {
  const filters: PaymentsFilterParams = {
    type: type === "income" || type === "expense" ? type : undefined,
    payment_status:
      paymentStatus === "plan" || paymentStatus === "paid" || paymentStatus === "overdue"
        ? paymentStatus
        : undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    page,
  };

  const result = await fetchPayments(orgId, filters);

  return (
    <PaymentsTab
      payments={result.data}
      totals={result.totals}
      total={result.total}
      page={result.page}
      pageSize={result.pageSize}
      filters={filters}
    />
  );
}

async function InvoicesTabLoader({
  orgId,
  page,
}: {
  orgId: string;
  page: number;
}) {
  const filters: SupplierInvoicesFilterParams = { page };

  const result = await fetchSupplierInvoices(orgId, filters);

  return (
    <SupplierInvoicesTab
      invoices={result.data}
      currencyTotals={result.currency_totals}
      total={result.total}
      page={result.page}
      pageSize={result.pageSize}
      filters={filters}
    />
  );
}
