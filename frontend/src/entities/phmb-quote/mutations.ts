import { createClient } from "@/shared/lib/supabase/client";
import type { CreatePhmbQuoteInput, CustomerSearchResult } from "./types";

async function generateIdnQuote(
  supabase: ReturnType<typeof createClient>,
  orgId: string
): Promise<string> {
  const now = new Date();
  const monthPrefix = `Q-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}-`;

  const { data } = await supabase
    .from("quotes")
    .select("idn_quote")
    .eq("organization_id", orgId)
    .like("idn_quote", `${monthPrefix}%`)
    .order("idn_quote", { ascending: false })
    .limit(1);

  let nextNum = 1;
  if (data && data.length > 0 && data[0].idn_quote) {
    const parts = data[0].idn_quote.split("-");
    const lastNum = parseInt(parts[parts.length - 1], 10);
    if (!isNaN(lastNum)) {
      nextNum = lastNum + 1;
    }
  }

  return `${monthPrefix}${String(nextNum).padStart(4, "0")}`;
}

export async function createPhmbQuote(
  orgId: string,
  userId: string,
  input: CreatePhmbQuoteInput
): Promise<{ id: string }> {
  const supabase = createClient();

  const idnQuote = await generateIdnQuote(supabase, orgId);

  const { data, error } = await supabase
    .from("quotes")
    .insert({
      organization_id: orgId,
      idn_quote: idnQuote,
      title: "PHMB КП",
      customer_id: input.customer_id,
      currency: input.currency,
      seller_company_id: input.seller_company_id,
      is_phmb: true,
      phmb_advance_pct: input.phmb_advance_pct,
      phmb_payment_days: input.phmb_payment_days,
      phmb_markup_pct: input.phmb_markup_pct,
      status: "draft",
      created_by: userId,
      created_by_user_id: userId,
    })
    .select("id")
    .single();

  if (error) throw error;

  return { id: data.id };
}

export async function searchCustomers(
  query: string,
  orgId: string
): Promise<CustomerSearchResult[]> {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("customers")
    .select("id, name, inn")
    .eq("organization_id", orgId)
    .ilike("name", `%${query}%`)
    .order("name")
    .limit(10);

  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
    inn: row.inn,
  }));
}
