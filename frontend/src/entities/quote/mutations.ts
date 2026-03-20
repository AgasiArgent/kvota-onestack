import { createClient } from "@/shared/lib/supabase/client";

export interface CreateQuoteInput {
  customer_id: string;
  seller_company_id?: string;
  delivery_country?: string;
  delivery_city?: string;
  delivery_method?: string;
}

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

export async function createQuote(
  orgId: string,
  userId: string,
  input: CreateQuoteInput
): Promise<{ id: string }> {
  const supabase = createClient();

  // Retry IDN generation up to 3 times for concurrent creation
  let lastError: Error | null = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    const idnQuote = await generateIdnQuote(supabase, orgId);

    const { data, error } = await supabase
      .from("quotes")
      .insert({
        organization_id: orgId,
        idn_quote: idnQuote,
        title: idnQuote,
        customer_id: input.customer_id,
        seller_company_id: input.seller_company_id || null,
        delivery_country: input.delivery_country || null,
        delivery_city: input.delivery_city || null,
        delivery_method: input.delivery_method || null,
        status: "draft",
        workflow_status: "draft",
        currency: "USD",
        is_phmb: false,
        created_by: userId,
        created_by_user_id: userId,
      })
      .select("id")
      .single();

    if (!error) return { id: data.id };

    // If duplicate IDN (unique constraint), retry
    if (error.code === "23505") {
      lastError = new Error(`IDN conflict on attempt ${attempt + 1}`);
      continue;
    }

    throw error;
  }

  throw lastError ?? new Error("Failed to generate unique IDN");
}

export async function searchCustomers(
  query: string,
  orgId: string
): Promise<Array<{ id: string; name: string; inn: string | null }>> {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("customers")
    .select("id, name, inn")
    .eq("organization_id", orgId)
    .or(`name.ilike.%${query}%,inn.ilike.%${query}%`)
    .order("name")
    .limit(10);

  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
    inn: row.inn,
  }));
}

export async function fetchSellerCompanies(
  orgId: string
): Promise<Array<{ id: string; name: string }>> {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("seller_companies")
    .select("id, name")
    .eq("organization_id", orgId)
    .eq("is_active", true)
    .order("name");

  if (error) throw error;

  return (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
  }));
}

// ---------------------------------------------------------------------------
// Quote Detail mutations (for quote detail page migration)
// ---------------------------------------------------------------------------

export async function sendQuoteComment(
  quoteId: string,
  userId: string,
  body: string,
  mentions?: string[]
) {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("quote_comments")
    .insert({
      quote_id: quoteId,
      user_id: userId,
      body,
      mentions: mentions ?? [],
    })
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function updateQuoteItem(
  itemId: string,
  updates: Record<string, unknown>
) {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("quote_items")
    .update(updates)
    .eq("id", itemId)
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function assignItemsToInvoice(
  itemIds: string[],
  invoiceId: string
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("quote_items")
    .update({ invoice_id: invoiceId })
    .in("id", itemIds);

  if (error) throw error;
}
