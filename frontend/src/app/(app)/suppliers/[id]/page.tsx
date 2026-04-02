import { notFound, redirect } from "next/navigation";
import {
  fetchSupplierDetail,
  fetchSupplierContacts,
  fetchBrandAssignments,
} from "@/entities/supplier/queries";
import { getSessionUser } from "@/entities/user";
import { SupplierHeader } from "@/features/suppliers/ui/supplier-header";
import { SupplierTabs } from "@/features/suppliers/ui/supplier-tabs";
import { TabOverview } from "@/features/suppliers/ui/tab-overview";
import { TabBrands } from "@/features/suppliers/ui/tab-brands";
import { TabContacts } from "@/features/suppliers/ui/tab-contacts";
import type { SupplierDetail } from "@/entities/supplier/types";

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}

export default async function SupplierDetailPage({ params, searchParams }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  const isAllowed =
    user.roles.includes("admin") || user.roles.includes("procurement") || user.roles.includes("procurement_senior");
  if (!isAllowed) redirect("/");

  const { id } = await params;
  const { tab = "overview" } = await searchParams;

  const supplier = await fetchSupplierDetail(id);
  if (!supplier) notFound();

  return (
    <div>
      <SupplierHeader supplier={supplier} />
      <SupplierTabs supplierId={id} activeTab={tab}>
        {tab === "overview" && <TabOverview supplier={supplier} />}
        {tab === "brands" && <BrandsContent supplierId={id} />}
        {tab === "contacts" && <ContactsContent supplierId={id} supplier={supplier} />}
      </SupplierTabs>
    </div>
  );
}

async function BrandsContent({ supplierId }: { supplierId: string }) {
  const brands = await fetchBrandAssignments(supplierId);
  return <TabBrands supplierId={supplierId} brands={brands} />;
}

async function ContactsContent({
  supplierId,
  supplier,
}: {
  supplierId: string;
  supplier: SupplierDetail;
}) {
  const contacts = await fetchSupplierContacts(supplierId);
  return <TabContacts supplierId={supplierId} contacts={contacts} />;
}
