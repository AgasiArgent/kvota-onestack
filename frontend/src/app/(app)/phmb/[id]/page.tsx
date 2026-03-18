import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  resolvePhmbQuoteId,
  fetchPhmbQuoteDetail,
  fetchPhmbQuoteItems,
  fetchPhmbVersions,
} from "@/entities/phmb-quote";
import { QuoteWorkspace } from "@/features/phmb/ui/quote-workspace";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PhmbWorkspacePage({ params }: Props) {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const isSalesOrAdmin =
    user.roles.includes("admin") ||
    user.roles.includes("sales") ||
    user.roles.includes("training_manager");

  if (!isSalesOrAdmin) redirect("/dashboard");
  if (!user.orgId) redirect("/dashboard");

  const { id: rawId } = await params;

  const quoteId = await resolvePhmbQuoteId(rawId);
  if (!quoteId) redirect("/phmb");

  const [quote, items, versions] = await Promise.all([
    fetchPhmbQuoteDetail(quoteId),
    fetchPhmbQuoteItems(quoteId),
    fetchPhmbVersions(quoteId),
  ]);

  if (!quote) redirect("/phmb");

  return (
    <QuoteWorkspace
      quote={quote}
      items={items}
      versions={versions}
      orgId={user.orgId}
    />
  );
}
