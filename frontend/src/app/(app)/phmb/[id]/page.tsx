import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import {
  fetchPhmbQuoteDetail,
  fetchPhmbQuoteItems,
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

  const { id } = await params;

  const [quote, items] = await Promise.all([
    fetchPhmbQuoteDetail(id),
    fetchPhmbQuoteItems(id),
  ]);

  if (!quote) redirect("/phmb");

  return (
    <QuoteWorkspace
      quote={quote}
      items={items}
      orgId={user.orgId}
    />
  );
}
