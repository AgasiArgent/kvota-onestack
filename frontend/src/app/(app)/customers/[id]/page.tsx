import { notFound } from "next/navigation";
import {
  fetchCustomerDetail,
  fetchCustomerStats,
  fetchCustomerContacts,
  fetchCustomerCalls,
  fetchCustomerQuotes,
  fetchCustomerSpecs,
  fetchCustomerContracts,
  fetchCustomerPositions,
  fetchOrgUsers,
} from "@/entities/customer";
import type { Customer } from "@/entities/customer";
import { CustomerHeader } from "@/features/customers/ui/customer-header";
import { CustomerTabs } from "@/features/customers/ui/customer-tabs";
import { TabOverview } from "@/features/customers/ui/tab-overview";
import { TabCRM } from "@/features/customers/ui/tab-crm";
import { TabDocuments } from "@/features/customers/ui/tab-documents";
import { TabPositions } from "@/features/customers/ui/tab-positions";

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string; subtab?: string }>;
}

export default async function CustomerDetailPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { tab = "overview", subtab } = await searchParams;

  const customer = await fetchCustomerDetail(id);
  if (!customer) notFound();

  return (
    <div>
      <CustomerHeader customer={customer} />
      <CustomerTabs customerId={id} activeTab={tab}>
        {tab === "overview" && <OverviewContent customerId={id} customer={customer} />}
        {tab === "crm" && <CRMContent customerId={id} customer={customer} />}
        {tab === "documents" && <DocumentsContent customerId={id} subtab={subtab} />}
        {tab === "positions" && <PositionsContent customerId={id} />}
      </CustomerTabs>
    </div>
  );
}

async function OverviewContent({
  customerId,
  customer,
}: {
  customerId: string;
  customer: Customer;
}) {
  const stats = await fetchCustomerStats(customerId);
  return <TabOverview customer={customer} stats={stats} />;
}

async function CRMContent({
  customerId,
  customer,
}: {
  customerId: string;
  customer: Customer;
}) {
  const [contacts, calls, orgUsers] = await Promise.all([
    fetchCustomerContacts(customerId),
    fetchCustomerCalls(customerId),
    fetchOrgUsers(customer.organization_id),
  ]);
  return <TabCRM customer={customer} contacts={contacts} calls={calls} orgUsers={orgUsers} />;
}

async function DocumentsContent({
  customerId,
  subtab,
}: {
  customerId: string;
  subtab?: string;
}) {
  const [quotes, specs, contracts] = await Promise.all([
    fetchCustomerQuotes(customerId),
    fetchCustomerSpecs(customerId),
    fetchCustomerContracts(customerId),
  ]);
  return (
    <TabDocuments
      customerId={customerId}
      quotes={quotes}
      specs={specs}
      contracts={contracts}
      initialSubTab={subtab}
    />
  );
}

async function PositionsContent({ customerId }: { customerId: string }) {
  const positions = await fetchCustomerPositions(customerId);
  return <TabPositions positions={positions} />;
}
