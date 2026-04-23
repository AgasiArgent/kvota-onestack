import { notFound, redirect } from "next/navigation";
import {
  fetchCustomerDetail,
  canAccessCustomer,
  fetchCustomerStats,
  fetchCustomerContacts,
  fetchCustomerCalls,
  fetchCustomerQuotes,
  fetchCustomerSpecs,
  fetchCustomerContracts,
  fetchCustomerPositions,
  fetchCustomerAssignees,
  fetchOrgUsers,
} from "@/entities/customer";
import type { Customer } from "@/entities/customer";
import { getSessionUser } from "@/entities/user";
import { fetchEntityNotes } from "@/entities/entity-note/queries";
import { EntityNotesPanel } from "@/entities/entity-note";
import { CustomerHeader } from "@/features/customers/ui/customer-header";
import { CustomerTabs } from "@/features/customers/ui/customer-tabs";
import { TabOverview } from "@/features/customers/ui/tab-overview";
import { TabCRM } from "@/features/customers/ui/tab-crm";
import { TabDocuments } from "@/features/customers/ui/tab-documents";
import { TabPositions } from "@/features/customers/ui/tab-positions";
import { TabAssignees } from "@/features/customers/ui/tab-assignees";

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string; subtab?: string }>;
}

export default async function CustomerDetailPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { tab = "overview", subtab } = await searchParams;

  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const [customer, hasAccess] = await Promise.all([
    fetchCustomerDetail(id, user.orgId),
    canAccessCustomer(id, { id: user.id, roles: user.roles, orgId: user.orgId }),
  ]);
  if (!customer || !hasAccess) notFound();

  return (
    <div>
      <CustomerHeader customer={customer} orgId={user.orgId} userId={user.id} />
      <CustomerTabs customerId={id} activeTab={tab}>
        {tab === "overview" && (
          <OverviewContent
            customerId={id}
            customer={customer}
            userId={user.id}
            userRoles={user.roles}
          />
        )}
        {tab === "crm" && <CRMContent customerId={id} customer={customer} />}
        {tab === "documents" && <DocumentsContent customerId={id} subtab={subtab} />}
        {tab === "positions" && <PositionsContent customerId={id} />}
        {tab === "assignees" && <AssigneesContent customerId={id} orgId={user.orgId} userRoles={user.roles} />}
      </CustomerTabs>
    </div>
  );
}

async function OverviewContent({
  customerId,
  customer,
  userId,
  userRoles,
}: {
  customerId: string;
  customer: Customer;
  userId: string;
  userRoles: string[];
}) {
  const [stats, notes] = await Promise.all([
    fetchCustomerStats(customerId),
    fetchEntityNotes("customer", customerId),
  ]);
  return (
    <div className="space-y-6">
      <TabOverview customer={customer} stats={stats} />
      <EntityNotesPanel
        entityType="customer"
        entityId={customerId}
        initialNotes={notes}
        currentUser={{ id: userId, roles: userRoles }}
        title="Заметки о клиенте"
      />
    </div>
  );
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

async function AssigneesContent({
  customerId,
  orgId,
  userRoles,
}: {
  customerId: string;
  orgId: string;
  userRoles: string[];
}) {
  const [assignees, orgUsers] = await Promise.all([
    fetchCustomerAssignees(customerId),
    fetchOrgUsers(orgId),
  ]);
  const canManage =
    userRoles.includes("admin") || userRoles.includes("head_of_sales");
  return (
    <TabAssignees
      customerId={customerId}
      assignees={assignees}
      salesUsers={orgUsers}
      canManage={canManage}
    />
  );
}
