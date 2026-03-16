import { redirect } from "next/navigation";
import { getSessionUser } from "@/entities/user";
import { createAdminClient } from "@/shared/lib/supabase/server";
import { ApprovalsList } from "@/features/approvals";

interface QuoteRow {
  id: string;
  idn_quote: string;
  total_amount: number;
  currency: string;
  approval_reason: string | null;
  approval_justification: string | null;
  updated_at: string | null;
  customers: { name: string | null; inn: string | null } | null;
}

export default async function ApprovalsPage() {
  const user = await getSessionUser();
  if (!user) redirect("/login");

  const hasAccess =
    user.roles.includes("admin") || user.roles.includes("top_manager");
  if (!hasAccess) redirect("/");

  const admin = createAdminClient();
  const { data } = await admin
    .from("quotes")
    .select(
      "id, idn_quote, total_amount, currency, approval_reason, approval_justification, updated_at, customers!customer_id(name, inn)"
    )
    .eq("organization_id", user.orgId!)
    .eq("workflow_status", "pending_approval")
    .order("updated_at", { ascending: false });

  // Cast through unknown: generated types lack FK relationships metadata,
  // so Supabase TS emits SelectQueryError for the join — runtime is correct.
  const quotes = (data ?? []) as unknown as QuoteRow[];

  return <ApprovalsList quotes={quotes} />;
}
