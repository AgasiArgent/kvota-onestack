import { notFound, redirect } from "next/navigation";
import {
  fetchSupplierDetail,
  fetchSupplierContacts,
  fetchBrandAssignments,
  fetchSupplierAssignees,
  fetchSupplierQuoteItems,
  fetchProcurementUsers,
  canAccessSupplier,
} from "@/entities/supplier/queries";
import { getSessionUser } from "@/entities/user/server";
import { hasProcurementAccess, canManageSupplierAssignees } from "@/shared/lib/roles";
import { SupplierHeader } from "@/features/suppliers/ui/supplier-header";
import { SupplierTabs } from "@/features/suppliers/ui/supplier-tabs";
import { TabOverview } from "@/features/suppliers/ui/tab-overview";
import { TabBrands } from "@/features/suppliers/ui/tab-brands";
import { TabContacts } from "@/features/suppliers/ui/tab-contacts";
import { TabAssignees } from "@/features/suppliers/ui/tab-assignees";
import { TabPositions } from "@/features/suppliers/ui/tab-positions";

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}

export default async function SupplierDetailPage({ params, searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  if (!hasProcurementAccess(user.roles)) redirect("/");

  const { id } = await params;
  const { tab = "overview" } = await searchParams;

  const [supplier, hasAccess] = await Promise.all([
    fetchSupplierDetail(id),
    canAccessSupplier(id, { id: user.id, roles: user.roles }),
  ]);
  if (!supplier || !hasAccess) notFound();

  return (
    <div>
      <SupplierHeader supplier={supplier} />
      <SupplierTabs supplierId={id} activeTab={tab}>
        {tab === "overview" && <TabOverview supplier={supplier} />}
        {tab === "brands" && <BrandsContent supplierId={id} />}
        {tab === "contacts" && <ContactsContent supplierId={id} />}
        {tab === "positions" && <PositionsContent supplierId={id} />}
        {tab === "assignees" && (
          <AssigneesContent supplierId={id} orgId={user.orgId} userRoles={user.roles} />
        )}
      </SupplierTabs>
    </div>
  );
}

async function BrandsContent({ supplierId }: { supplierId: string }) {
  const brands = await fetchBrandAssignments(supplierId);
  return <TabBrands supplierId={supplierId} brands={brands} />;
}

async function ContactsContent({ supplierId }: { supplierId: string }) {
  const contacts = await fetchSupplierContacts(supplierId);
  return <TabContacts supplierId={supplierId} contacts={contacts} />;
}

async function PositionsContent({ supplierId }: { supplierId: string }) {
  const items = await fetchSupplierQuoteItems(supplierId);
  return <TabPositions items={items} />;
}

async function AssigneesContent({
  supplierId,
  orgId,
  userRoles,
}: {
  supplierId: string;
  orgId: string;
  userRoles: string[];
}) {
  const canManage = canManageSupplierAssignees(userRoles);

  const [assignees, procurementUsers] = await Promise.all([
    fetchSupplierAssignees(supplierId),
    canManage ? fetchProcurementUsers(orgId) : Promise.resolve([]),
  ]);

  return (
    <TabAssignees
      supplierId={supplierId}
      assignees={assignees}
      procurementUsers={procurementUsers}
      canManage={canManage}
    />
  );
}
