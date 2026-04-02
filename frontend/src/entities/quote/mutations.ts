import { createClient } from "@/shared/lib/supabase/client";
import { escapePostgrestFilter } from "@/shared/lib/supabase/escape-filter";

// ---------------------------------------------------------------------------
// Workflow transition via Python API (handles validation, audit log, timestamps)
// ---------------------------------------------------------------------------

async function callWorkflowTransition(
  quoteId: string,
  body: Record<string, unknown>
): Promise<{ from_status: string; to_status: string }> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`/api/quotes/${quoteId}/workflow/transition`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
    },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  if (!res.ok || !data.success) {
    throw new Error(data.error || "Workflow transition failed");
  }
  return data;
}

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
    .or(`name.ilike.%${escapePostgrestFilter(query)}%,inn.ilike.%${escapePostgrestFilter(query)}%`)
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

export async function unassignItemFromInvoice(itemId: string) {
  const supabase = createClient();

  const { error } = await supabase
    .from("quote_items")
    .update({ invoice_id: null })
    .eq("id", itemId);

  if (error) throw error;
}

// ---------------------------------------------------------------------------
// Quote Item CRUD
// ---------------------------------------------------------------------------

export async function createQuoteItem(
  quoteId: string,
  item: {
    product_name: string;
    brand?: string;
    product_code?: string;
    quantity: number;
    unit?: string;
  }
) {
  const supabase = createClient();

  // Determine next position
  const { data: existing } = await supabase
    .from("quote_items")
    .select("position")
    .eq("quote_id", quoteId)
    .order("position", { ascending: false })
    .limit(1);

  const nextPosition = (existing?.[0]?.position ?? 0) + 1;

  const { data, error } = await supabase
    .from("quote_items")
    .insert({
      quote_id: quoteId,
      product_name: item.product_name,
      brand: item.brand || null,
      product_code: item.product_code || null,
      quantity: item.quantity,
      unit: item.unit || null,
      position: nextPosition,
    })
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function deleteQuoteItem(itemId: string) {
  const supabase = createClient();

  const { error } = await supabase
    .from("quote_items")
    .delete()
    .eq("id", itemId);

  if (error) throw error;
}

// ---------------------------------------------------------------------------
// Invoice CRUD
// ---------------------------------------------------------------------------

export async function createInvoice(data: {
  quote_id: string;
  idn_quote: string;
  supplier_id?: string;
  buyer_company_id?: string;
  pickup_city?: string;
  currency?: string;
  total_weight_kg?: number;
  total_volume_m3?: number;
}) {
  const supabase = createClient();

  // Generate invoice number: INV-{idx}-{idn_quote}
  const { count } = await supabase
    .from("invoices")
    .select("id", { count: "exact", head: true })
    .eq("quote_id", data.quote_id);

  const idx = (count ?? 0) + 1;
  const invoiceNumber = `INV-${String(idx).padStart(2, "0")}-${data.idn_quote}`;

  const { data: invoice, error } = await supabase
    .from("invoices")
    .insert({
      quote_id: data.quote_id,
      invoice_number: invoiceNumber,
      supplier_id: data.supplier_id || null,
      buyer_company_id: data.buyer_company_id || null,
      pickup_city: data.pickup_city || null,
      currency: data.currency || "USD",
      total_weight_kg: data.total_weight_kg ?? 0,
      total_volume_m3: data.total_volume_m3 ?? null,
    })
    .select("id, invoice_number")
    .single();

  if (error) throw error;
  return invoice;
}

export async function updateInvoice(
  invoiceId: string,
  updates: Record<string, unknown>
) {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("invoices")
    .update(updates)
    .eq("id", invoiceId)
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function deleteInvoice(invoiceId: string) {
  const supabase = createClient();

  // Unassign items first
  await supabase
    .from("quote_items")
    .update({ invoice_id: null })
    .eq("invoice_id", invoiceId);

  const { error } = await supabase
    .from("invoices")
    .delete()
    .eq("id", invoiceId);

  if (error) throw error;
}

// ---------------------------------------------------------------------------
// Workflow status transitions
// ---------------------------------------------------------------------------

export async function updateQuoteWorkflowStatus(
  quoteId: string,
  status: string,
  extras?: Record<string, unknown>
) {
  const supabase = createClient();

  const { error } = await supabase
    .from("quotes")
    .update({ workflow_status: status, ...extras })
    .eq("id", quoteId);

  if (error) throw error;
}

export async function submitToProcurement(quoteId: string) {
  return updateQuoteWorkflowStatus(quoteId, "pending_procurement");
}

export async function completeProcurement(quoteId: string) {
  return updateQuoteWorkflowStatus(quoteId, "procurement_complete", {
    procurement_completed_at: new Date().toISOString(),
  });
}

export async function completeLogistics(quoteId: string) {
  return updateQuoteWorkflowStatus(quoteId, "pending_customs", {
    logistics_completed_at: new Date().toISOString(),
  });
}

export async function completeCustoms(quoteId: string) {
  await callWorkflowTransition(quoteId, { action: "complete_customs" });
}

export async function skipCustoms(quoteId: string) {
  await callWorkflowTransition(quoteId, {
    to_status: "pending_sales_review",
  });
}

export async function sendToClient(quoteId: string) {
  return updateQuoteWorkflowStatus(quoteId, "sent_to_client", {
    sent_at: new Date().toISOString(),
  });
}

export async function acceptQuote(quoteId: string) {
  return updateQuoteWorkflowStatus(quoteId, "pending_spec_control");
}

export async function rejectQuote(
  quoteId: string,
  reason: string,
  comment: string
) {
  return updateQuoteWorkflowStatus(quoteId, "rejected", {
    rejection_reason: reason,
    rejection_comment: comment,
    rejected_at: new Date().toISOString(),
  });
}

export async function cancelQuote(quoteId: string, reason: string) {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`/api/quotes/${quoteId}/cancel`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
    },
    body: JSON.stringify({ reason }),
  });

  const data = await res.json();
  if (!res.ok || !data.success) {
    throw new Error(data.error || "Не удалось отменить КП");
  }
}

export async function requestChanges(
  quoteId: string,
  changeType: string,
  comment: string
) {
  return updateQuoteWorkflowStatus(quoteId, "draft", {
    revision_department: changeType,
    revision_comment: comment,
    revision_returned_at: new Date().toISOString(),
  });
}

// ---------------------------------------------------------------------------
// Logistics expenses CRUD
// ---------------------------------------------------------------------------

export async function createLogisticsExpense(data: {
  invoice_id: string;
  expense_type: string;
  description?: string;
  amount: number;
  currency: string;
}) {
  const supabase = createClient();

  const { data: expense, error } = await supabase
    .from("logistics_additional_expenses")
    .insert({
      invoice_id: data.invoice_id,
      expense_type: data.expense_type,
      description: data.description || null,
      amount: data.amount,
      currency: data.currency,
    })
    .select()
    .single();

  if (error) throw error;
  return expense;
}

export async function updateLogisticsExpense(
  expenseId: string,
  updates: Record<string, unknown>
) {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("logistics_additional_expenses")
    .update(updates)
    .eq("id", expenseId)
    .select()
    .single();

  if (error) throw error;
  return data;
}

export async function deleteLogisticsExpense(expenseId: string) {
  const supabase = createClient();

  const { error } = await supabase
    .from("logistics_additional_expenses")
    .delete()
    .eq("id", expenseId);

  if (error) throw error;
}

// ---------------------------------------------------------------------------
// Logistics route segment updates (on invoices table)
// ---------------------------------------------------------------------------

export async function updateInvoiceLogistics(
  invoiceId: string,
  updates: Record<string, unknown>
) {
  return updateInvoice(invoiceId, updates);
}

// ---------------------------------------------------------------------------
// Quote control workflow mutations
// ---------------------------------------------------------------------------

export async function approveQuote(
  quoteId: string,
  userId: string
): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("quotes")
    .update({
      workflow_status: "approved",
      quote_controller_id: userId,
      quote_control_completed_at: new Date().toISOString(),
    })
    .eq("id", quoteId);

  if (error) throw error;
}

export async function returnQuoteForRevision(
  quoteId: string,
  userId: string,
  comment: string
): Promise<void> {
  const supabase = createClient();

  const { error: updateError } = await supabase
    .from("quotes")
    .update({ workflow_status: "revision" })
    .eq("id", quoteId);

  if (updateError) throw updateError;

  const { error: commentError } = await supabase
    .from("quote_comments")
    .insert({
      quote_id: quoteId,
      user_id: userId,
      body: `[Возврат на доработку] ${comment}`,
      created_at: new Date().toISOString(),
    });

  if (commentError) throw commentError;
}

export async function escalateQuote(
  quoteId: string,
  userId: string,
  comment: string
): Promise<void> {
  const supabase = createClient();

  const { error: updateError } = await supabase
    .from("quotes")
    .update({ workflow_status: "pending_approval" })
    .eq("id", quoteId);

  if (updateError) throw updateError;

  const { error: commentError } = await supabase
    .from("quote_comments")
    .insert({
      quote_id: quoteId,
      user_id: userId,
      body: `[На согласование] ${comment}`,
      created_at: new Date().toISOString(),
    });

  if (commentError) throw commentError;
}
