import { redirect, notFound } from "next/navigation";
import { getSessionUser } from "@/entities/user/server";
import {
  fetchCurrencyInvoiceDetail,
  fetchCompanyOptions,
  canAccessCurrencyInvoices,
} from "@/entities/currency-invoice";
import { CIDetail } from "@/features/currency-invoices";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function CurrencyInvoiceDetailPage({ params }: Props) {
  const user = await getSessionUser();
  if (!user?.orgId) redirect("/login");

  if (!canAccessCurrencyInvoices(user.roles)) {
    redirect("/quotes");
  }

  const { id } = await params;

  const [invoice, companyOptions] = await Promise.all([
    fetchCurrencyInvoiceDetail(id, user.orgId),
    fetchCompanyOptions(user.orgId),
  ]);

  if (!invoice) notFound();

  return (
    <CIDetail
      invoice={invoice}
      sellers={companyOptions.sellers}
      buyers={companyOptions.buyers}
      userRoles={user.roles}
      orgId={user.orgId}
    />
  );
}
