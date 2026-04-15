import { createClient } from "@/shared/lib/supabase/client";
import { escapePostgrestFilter } from "@/shared/lib/supabase/escape-filter";
import { findCountryByName } from "@/shared/ui/geo";

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
  incoterms?: string;
  delivery_priority?: string;
  valid_until?: string;
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
        incoterms: input.incoterms || null,
        delivery_priority: input.delivery_priority || null,
        valid_until: input.valid_until || null,
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
  mentions?: string[],
  attachmentDocumentIds?: string[]
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

  // Link uploaded attachments to this comment. Documents were inserted
  // earlier by useChatAttachments with comment_id=null; we set it here so
  // they can be queried as chat media on the documents tab.
  if (attachmentDocumentIds && attachmentDocumentIds.length > 0) {
    const { error: linkError } = await supabase
      .from("documents")
      .update({ comment_id: data.id })
      .in("id", attachmentDocumentIds);
    if (linkError) throw linkError;
  }

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

  if (itemIds.length === 0) return;

  // 1) Legacy pointer + composition pointer move in lockstep on initial
  //    assignment. If the user later opens the CompositionPicker and picks
  //    a different invoice for an item, composition_selected_invoice_id
  //    will diverge from invoice_id — which is fine (Decision #1).
  const { error } = await supabase
    .from("quote_items")
    .update({
      invoice_id: invoiceId,
      composition_selected_invoice_id: invoiceId,
    })
    .in("id", itemIds);
  if (error) throw error;

  // 2) Phase 5b — insert invoice_item_prices rows for every assigned item
  //    so the CompositionPicker has data to show and the calculation path
  //    (composition_service.get_composed_items) finds an overlay source.
  //    Two queries (no FK join) to sidestep the empty-Relationships
  //    limitation in generated database.types.ts (see database.md).
  const { data: items, error: fetchErr } = await supabase
    .from("quote_items")
    .select(
      "id, quote_id, purchase_price_original, purchase_currency, base_price_vat, price_includes_vat"
    )
    .in("id", itemIds);
  if (fetchErr) throw fetchErr;
  if (!items || items.length === 0) return;

  const quoteIds = Array.from(new Set(items.map((i) => i.quote_id)));
  const { data: quotes, error: quotesErr } = await supabase
    .from("quotes")
    .select("id, organization_id")
    .in("id", quoteIds)
    .is("deleted_at", null);
  if (quotesErr) throw quotesErr;

  const orgByQuote = new Map<string, string>(
    (quotes ?? []).map((q) => [q.id, q.organization_id])
  );

  const iipRows = items
    .map((item) => {
      const orgId = orgByQuote.get(item.quote_id);
      if (!orgId) return null; // skip items whose quote lacks org_id
      return {
        invoice_id: invoiceId,
        quote_item_id: item.id,
        organization_id: orgId,
        purchase_price_original:
          Number(item.purchase_price_original ?? item.base_price_vat ?? 0),
        purchase_currency: item.purchase_currency ?? "USD",
        base_price_vat: item.base_price_vat,
        price_includes_vat: item.price_includes_vat ?? false,
        version: 1,
      };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null);

  if (iipRows.length === 0) return;

  // Upsert with ignoreDuplicates: re-assigning the same items to the same
  // invoice is a no-op on the junction. Different (invoice, item) pairs
  // accumulate — that's the point, alternatives build up as multi-supplier
  // procurement progresses.
  const { error: iipError } = await supabase
    .from("invoice_item_prices")
    .upsert(iipRows, {
      onConflict: "invoice_id,quote_item_id,version",
      ignoreDuplicates: true,
    });
  if (iipError) throw iipError;
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

export async function createQuoteItemsBatch(
  quoteId: string,
  items: {
    product_name: string;
    brand?: string;
    product_code?: string;
    quantity: number;
    unit?: string;
  }[]
) {
  if (items.length === 0) return [];

  const supabase = createClient();

  const { data: existing } = await supabase
    .from("quote_items")
    .select("position")
    .eq("quote_id", quoteId)
    .order("position", { ascending: false })
    .limit(1);

  const basePosition = (existing?.[0]?.position ?? 0) + 1;

  const rows = items.map((item, i) => ({
    quote_id: quoteId,
    product_name: item.product_name,
    brand: item.brand || null,
    product_code: item.product_code || null,
    quantity: item.quantity,
    unit: item.unit || null,
    position: basePosition + i,
  }));

  const { data, error } = await supabase
    .from("quote_items")
    .insert(rows)
    .select();

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

export interface CargoPlaceInput {
  weight_kg: number;
  length_mm: number;
  width_mm: number;
  height_mm: number;
}

export type CreateInvoiceBypassReason = "same_supplier" | "new_supplier" | null;

export async function createInvoice(data: {
  quote_id: string;
  idn_quote: string;
  supplier_id?: string;
  buyer_company_id?: string;
  pickup_city?: string;
  /**
   * Explicit pickup country (Russian display name) chosen in the modal.
   * When set, overrides both sibling inheritance (Phase 5b bypass) and the
   * supplier-derived default (Phase 5a/Phase 3).
   */
  pickup_country_override?: string | null;
  /**
   * Explicit ISO 3166-1 alpha-2 code chosen in the modal. When set, overrides
   * the code resolved from supplier.country via findCountryByName.
   */
  pickup_country_code?: string | null;
  /** Incoterms 2020 code picked in the modal, e.g. "FOB", "CIF". */
  supplier_incoterms?: string | null;
  currency?: string;
  boxes: CargoPlaceInput[];
}): Promise<{
  id: string;
  invoice_number: string;
  bypass_reason: CreateInvoiceBypassReason;
}> {
  const supabase = createClient();

  // Compute totals from boxes
  const totalWeightKg = data.boxes.reduce((sum, b) => sum + b.weight_kg, 0);
  const totalVolumeM3 = data.boxes.reduce(
    (sum, b) => sum + (b.length_mm * b.width_mm * b.height_mm) / 1e9,
    0
  );

  // Phase 5b bypass detection (Decision #6) + Phase 3 pickup_country_code/incoterms:
  //   1. If the caller passes pickup_country_override (Phase 3 modal), that wins
  //      absolutely.
  //   2. Else if the quote already has another invoice from the same supplier
  //      (Phase 5b "same_supplier" bypass), inherit pickup fields from that
  //      sibling invoice — the user already filled them on the first KP from
  //      this supplier. Re-entering is friction.
  //   3. Else (new_supplier path), derive pickup_country from suppliers.country
  //      as in Phase 5a (Bug FB-260410-110450-4b85 fix: keeps logistics
  //      auto-assignment working).
  //
  //   After pickup_country is determined, resolve the alpha-2 code via
  //   ICU-backed findCountryByName (Phase 3) — caller-provided code wins,
  //   otherwise derive from the text name. Graceful degradation to null for
  //   legacy free-text country values ICU doesn't know.
  let pickupCountry: string | null = data.pickup_country_override ?? null;
  let pickupCity: string | null = data.pickup_city ?? null;
  let bypassReason: CreateInvoiceBypassReason = null;

  if (data.supplier_id) {
    const { data: sibling, error: siblingError } = await supabase
      .from("invoices")
      .select("id, pickup_country, pickup_city")
      .eq("quote_id", data.quote_id)
      .eq("supplier_id", data.supplier_id)
      .limit(1)
      .maybeSingle();
    if (siblingError) throw siblingError;

    if (sibling) {
      // Same-supplier bypass: inherit pickup from sibling when user didn't
      // explicitly override. Do NOT fall through to suppliers.country lookup.
      bypassReason = "same_supplier";
      pickupCountry = pickupCountry ?? sibling.pickup_country ?? null;
      pickupCity = pickupCity ?? sibling.pickup_city ?? null;
    } else {
      // New-supplier path: derive from suppliers.country if caller didn't
      // provide it. This preserves the Phase 5a auto-fill so logistics
      // auto-assignment keeps working.
      bypassReason = "new_supplier";
      if (!pickupCountry) {
        const { data: supplier, error: supplierError } = await supabase
          .from("suppliers")
          .select("country")
          .eq("id", data.supplier_id)
          .maybeSingle();
        if (supplierError) throw supplierError;
        pickupCountry = supplier?.country ?? null;
      }
    }
  }

  let pickupCountryCode: string | null = data.pickup_country_code ?? null;
  if (!pickupCountryCode && pickupCountry) {
    const match = findCountryByName(pickupCountry, "ru");
    pickupCountryCode = match?.code ?? null;
  }

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
      pickup_city: pickupCity,
      pickup_country: pickupCountry,
      pickup_country_code: pickupCountryCode,
      supplier_incoterms: data.supplier_incoterms ?? null,
      currency: data.currency || "USD",
      total_weight_kg: totalWeightKg,
      total_volume_m3: totalVolumeM3,
    })
    .select("id, invoice_number")
    .single();

  if (error) throw error;

  // Bulk-insert cargo places with sequential positions
  if (data.boxes.length > 0) {
    const cargoRows = data.boxes.map((box, i) => ({
      invoice_id: invoice.id,
      position: i + 1,
      weight_kg: box.weight_kg,
      length_mm: box.length_mm,
      width_mm: box.width_mm,
      height_mm: box.height_mm,
    }));

    const { error: cargoError } = await supabase
      .from("invoice_cargo_places")
      .insert(cargoRows);

    if (cargoError) throw cargoError;
  }

  return { ...invoice, bypass_reason: bypassReason };
}

// ---------------------------------------------------------------------------
// Cargo places query (client-side — used by invoice-card and logistics-invoice-row)
// ---------------------------------------------------------------------------

export async function fetchCargoPlaces(invoiceId: string) {
  const supabase = createClient();
  const { data } = await supabase
    .from("invoice_cargo_places")
    .select("*")
    .eq("invoice_id", invoiceId)
    .order("position", { ascending: true });
  return data ?? [];
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

export async function completeProcurement(quoteId: string) {
  const supabase = createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Batch-set all items to procurement_status='completed' before workflow transition.
  // The backend's check_all_procurement_complete requires this status on every item.
  const { error } = await supabase
    .from("quote_items")
    .update({
      procurement_status: "completed",
      procurement_completed_at: new Date().toISOString(),
      procurement_completed_by: user?.id ?? null,
    })
    .eq("quote_id", quoteId)
    .neq("is_unavailable", true);

  if (error) throw error;

  await callWorkflowTransition(quoteId, { action: "complete_procurement" });
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

export async function submitToProcurementWithChecklist(
  quoteId: string,
  checklist: {
    is_estimate: boolean;
    is_tender: boolean;
    direct_request: boolean;
    trading_org_request: boolean;
    equipment_description: string;
  }
): Promise<void> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`/api/quotes/${quoteId}/submit-procurement`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
    },
    body: JSON.stringify({ checklist }),
  });

  const data = await res.json();
  if (!res.ok || data.error) {
    throw new Error(data.error || "Не удалось передать в закупки");
  }
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

export async function patchQuote(
  quoteId: string,
  updates: Partial<{
    contact_person_id: string | null;
    delivery_address: string | null;
    delivery_priority: string | null;
  }>
): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("quotes")
    .update(updates)
    .eq("id", quoteId);

  if (error) throw error;
}

// ---------------------------------------------------------------------------
// Procurement substatus transitions (kanban)
// ---------------------------------------------------------------------------

export interface StatusHistoryEntry {
  id: string;
  quote_id: string;
  /**
   * Brand this transition applies to. `null` means a quote-level transition
   * (no brand scope); a string (possibly `""` for unbranded) means the
   * transition only moved that (quote, brand) slice on the kanban.
   */
  brand: string | null;
  from_status: string | null;
  to_status: string;
  from_substatus: string | null;
  to_substatus: string | null;
  transitioned_by: string | null;
  transitioned_by_name: string | null;
  reason: string | null;
  transitioned_at: string;
}

/**
 * GET /api/quotes/{id}/status-history — returns the full transition audit log
 * for a quote, ordered by transitioned_at.
 */
export async function fetchStatusHistory(
  quoteId: string
): Promise<StatusHistoryEntry[]> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`/api/quotes/${quoteId}/status-history`, {
    headers: {
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
    },
  });

  const json = await res.json();
  if (!res.ok || !json.success) return [];
  return (json.data ?? []) as StatusHistoryEntry[];
}

export interface SubstatusTransitionResult {
  quote_id: string;
  brand: string;
  procurement_substatus: string;
}

/**
 * POST /api/quotes/{id}/substatus — moves a (quote, brand) card between
 * procurement kanban columns. Backward moves require a non-empty reason
 * (validated server-side). `brand` is required; use `""` for unbranded slices.
 */
export async function transitionSubstatus(
  quoteId: string,
  brand: string,
  toSubstatus: string,
  reason?: string
): Promise<SubstatusTransitionResult> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`/api/quotes/${quoteId}/substatus`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
    },
    body: JSON.stringify({
      brand,
      to_substatus: toSubstatus,
      ...(reason ? { reason } : {}),
    }),
  });

  const json = await res.json();
  if (!res.ok || !json.success) {
    throw new Error(
      json?.error?.message ?? `Failed to transition (HTTP ${res.status})`
    );
  }
  return json.data as SubstatusTransitionResult;
}
