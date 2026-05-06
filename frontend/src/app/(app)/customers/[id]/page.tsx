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
  fetchCustomerDocuments,
  fetchCustomerPositions,
  fetchCustomerAssignees,
  fetchOrgUsers,
} from "@/entities/customer";
import type { Customer } from "@/entities/customer";
import { getSessionUser, fetchUserSalesGroupId } from "@/entities/user";
import { isSalesOnly } from "@/shared/lib/roles";
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

  // Resolve salesGroupId BEFORE the access check. canAccessCustomer needs
  // it to expand head_of_sales visibility to group members' assignments;
  // running it in parallel with this fetch (the previous shape) caused
  // every РОП to be denied access to subordinate customers (G1 / РОП-1).
  // Non-sales-only roles never hit the assigned-customers gate, so we
  // skip the lookup for them.
  const salesGroupId = isSalesOnly(user.roles)
    ? await fetchUserSalesGroupId(user.id, user.orgId)
    : null;

  const [customer, hasAccess] = await Promise.all([
    fetchCustomerDetail(id, user.orgId),
    canAccessCustomer(id, {
      id: user.id,
      roles: user.roles,
      orgId: user.orgId,
      salesGroupId,
    }),
  ]);
  if (!customer || !hasAccess) notFound();

  return (
    <div>
      <CustomerHeader
        customer={customer}
        orgId={user.orgId}
        userId={user.id}
        userRoles={user.roles}
        salesGroupId={salesGroupId}
      />
      <CustomerTabs customerId={id} activeTab={tab}>
        {tab === "overview" && (
          <OverviewContent
            customerId={id}
            customer={customer}
            userId={user.id}
            userRoles={user.roles}
          />
        )}
        {tab === "crm" && <CRMContent customerId={id} customer={customer} userId={user.id} />}
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
  userId,
}: {
  customerId: string;
  customer: Customer;
  userId: string;
}) {
  const [contacts, calls, orgUsers] = await Promise.all([
    fetchCustomerContacts(customerId),
    fetchCustomerCalls(customerId),
    fetchOrgUsers(customer.organization_id),
  ]);
  return (
    <TabCRM
      customer={customer}
      contacts={contacts}
      calls={calls}
      orgUsers={orgUsers}
      currentUserId={userId}
    />
  );
}

async function DocumentsContent({
  customerId,
  subtab,
}: {
  customerId: string;
  subtab?: string;
}) {
  const [quotes, specs, contracts, contractDocs, foundingDocs] =
    await Promise.all([
      fetchCustomerQuotes(customerId),
      fetchCustomerSpecs(customerId),
      fetchCustomerContracts(customerId),
      fetchCustomerDocuments(customerId, "contract"),
      fetchCustomerDocuments(customerId, "founding_docs"),
    ]);
  return (
    <TabDocuments
      customerId={customerId}
      quotes={quotes}
      specs={specs}
      contracts={contracts}
      contractDocs={contractDocs}
      foundingDocs={foundingDocs}
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
