import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  fetchPhmbQuotesList,
  fetchPhmbDefaults,
  fetchSellerCompanies,
} from "@/entities/phmb-quote";
import { PhmbRegistry } from "@/features/phmb";
import type { PhmbQuoteStatus } from "@/entities/phmb-quote";

interface Props {
  searchParams: Promise<{ search?: string; status?: string; page?: string }>;
}

const ALLOWED_STATUSES: PhmbQuoteStatus[] = [
  "draft",
  "waiting_prices",
  "ready",
];

export default async function PhmbPage({ searchParams }: Props) {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const isSalesOrAdmin =
    user.roles.includes("admin") ||
    user.roles.includes("sales") ||
    user.roles.includes("training_manager");

  if (!isSalesOrAdmin) redirect("/dashboard");
  if (!user.orgId) redirect("/dashboard");

  const params = await searchParams;
  const search = params.search ?? "";
  const statusParam = params.status ?? "";
  const status = ALLOWED_STATUSES.includes(statusParam as PhmbQuoteStatus)
    ? (statusParam as PhmbQuoteStatus)
    : undefined;
  const page = Math.max(1, parseInt(params.page ?? "1", 10));

  const [quotesResult, defaults, sellerCompanies] = await Promise.all([
    fetchPhmbQuotesList({ orgId: user.orgId, search, status, page }),
    fetchPhmbDefaults(user.orgId),
    fetchSellerCompanies(user.orgId),
  ]);

  return (
    <PhmbRegistry
      quotes={quotesResult.data}
      total={quotesResult.total}
      defaults={defaults}
      sellerCompanies={sellerCompanies}
      orgId={user.orgId}
      userId={user.id}
      initialSearch={search}
      initialStatus={status}
      initialPage={page}
    />
  );
}
