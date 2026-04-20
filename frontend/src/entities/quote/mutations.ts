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

/**
 * Resolve the organization_id for an invoice via its owning quote.
 *
 * `kvota.invoices` has no `organization_id` column (Phase 5d discovery): the
 * org boundary lives on `kvota.quotes`, and invoices inherit it through
 * `quote_id`. Used by assignment/split/merge to stamp the new
 * `invoice_items.organization_id` for RLS.
 *
 * Two round trips rather than a PostgREST FK embed so the shape stays simple
 * and easy to stub in tests.
 */
async function getInvoiceOrganizationId(
  supabase: ReturnType<typeof createClient>,
  invoiceId: string
): Promise<string> {
  const { data: inv, error: invErr } = await supabase
    .from("invoices")
    .select("quote_id")
    .eq("id", invoiceId)
    .single();
  if (invErr) throw invErr;
  if (!inv) throw new Error("invoice not found");

  const { data: quote, error: quoteErr } = await supabase
    .from("quotes")
    .select("organization_id")
    .eq("id", inv.quote_id)
    .single();
  if (quoteErr) throw quoteErr;
  if (!quote) throw new Error("quote not found");

  return quote.organization_id;
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

/**
 * Phase 5d Group 5 Appendix — supplier-side row update, writes to
 * kvota.invoice_items. Post Task 14, procurement-handsontable rows carry
 * invoice_items.id as rowId; this mutation targets that row directly.
 *
 * Mirrors `updateQuoteItem`'s shape but different table. Callers must not
 * pass customer-side fields (product_code, manufacturer_product_name,
 * name_en, is_unavailable, supplier_sku_note) — those remain on quote_items
 * and are not editable through the procurement editor.
 *
 * Bypasses the missing database.types.ts entry for invoice_items via the
 * same `any`-cast pattern used in assignItemsToInvoice / splitInvoiceItem /
 * mergeInvoiceItems above.
 */
export async function updateInvoiceItem(
  invoiceItemId: string,
  updates: Record<string, unknown>
) {
  const supabase = createClient();

  const { data, error } = await supabase
    .from("invoice_items")
    .update(updates)
    .eq("id", invoiceItemId)
    .select()
    .single();

  if (error) throw error;
  return data;
}

/**
 * Phase 5c assignment: non-destructive, writes to invoice_items +
 * invoice_item_coverage (the new schema). Each assignment creates one
 * invoice_item row per quote_item (seeded from quote_items defaults) plus a
 * matching coverage row with ratio=1. Re-assigning the same (invoice,
 * quote_item) pair is a no-op via ON CONFLICT DO NOTHING.
 *
 * Legacy writes (quote_items.invoice_id, invoice_item_prices) are removed —
 * both are dropped in migration 284.
 *
 * `invoice_items` and `invoice_item_coverage` are not yet in the generated
 * database.types.ts (migrations 281-282 added them). We bypass the missing
 * types via an `any`-cast on `from` — same pattern used in queries.ts for
 * stage_deadlines while the types generator catches up.
 *
 * Non-atomic: Supabase REST has no transaction support, so steps 4 (INSERT
 * invoice_items), 5 (INSERT invoice_item_coverage) and 6 (UPDATE quote_items
 * pointer) are separate network calls. If INSERT fails mid-way, re-run
 * assignment — the pre-check in step 3a skips already-covered quote_items
 * and the upsert in step 5 is duplicate-safe via ON CONFLICT DO NOTHING.
 * Orphan invoice_items from a partially-failed run remain in the invoice but
 * have no coverage row; the UI treats them as manual additions.
 */
export async function assignItemsToInvoice(
  itemIds: string[],
  invoiceId: string
) {
  if (itemIds.length === 0) return;

  const supabase = createClient();

  // 1. Fetch quote_items for seeding invoice_items defaults.
  //    Include every field build_calculation_inputs sees on the supplier
  //    side: name, SKU, brand, qty, idn_sku, vat_rate. Purchase price is
  //    left null here and filled by procurement in the invoice-card editor.
  const { data: items, error: itemsErr } = await supabase
    .from("quote_items")
    .select("id, quote_id, product_name, supplier_sku, brand, quantity, idn_sku, vat_rate")
    .in("id", itemIds);
  if (itemsErr) throw itemsErr;
  if (!items || items.length === 0) return;

  // 2. Resolve invoice organization_id via the owning quote (needed for RLS
  //    + invoice_items.organization_id). `kvota.invoices` has no
  //    organization_id column — it lives on kvota.quotes and is inherited
  //    through quote_id.
  const organizationId = await getInvoiceOrganizationId(supabase, invoiceId);

  // 3. Compute next position within target invoice (MAX + 1).
  const { data: posRow } = await supabase
    .from("invoice_items")
    .select("position")
    .eq("invoice_id", invoiceId)
    .order("position", { ascending: false })
    .limit(1);
  const startPos =
    (Array.isArray(posRow) && posRow.length > 0
      ? (posRow[0] as { position: number }).position
      : 0) + 1;

  // 3a. Pre-check coverage: skip quote_items that already have a coverage
  //     row in THIS invoice. Prevents creating ghost invoice_items on
  //     re-run of a partially-succeeded assignment. Without this step, the
  //     INSERT at step 4 would create a fresh invoice_item while the old
  //     coverage row still points at the prior invoice_item, leaving two
  //     supplier positions for the same quote_item.
  const { data: existingCov, error: existCovErr } = await supabase
    .from("invoice_item_coverage")
    .select("quote_item_id, invoice_items!inner(invoice_id)")
    .in("quote_item_id", itemIds);
  if (existCovErr) throw existCovErr;

  const alreadyCoveredQiIds = new Set<string>(
    (
      (existingCov ?? []) as unknown as Array<{
        quote_item_id: string;
        invoice_items: { invoice_id: string };
      }>
    )
      .filter((r) => r.invoice_items?.invoice_id === invoiceId)
      .map((r) => r.quote_item_id)
  );

  const itemsToInsert = items.filter(
    (item) => !alreadyCoveredQiIds.has(item.id)
  );

  if (itemsToInsert.length > 0) {
    // 4. Insert invoice_items — one row per newly-assigned quote_item, with
    //    defaults copied from quote_items. Position is sequential per
    //    insertion order. version=1 matches Phase 5b semantics (immutable
    //    until frozen).
    const iiRows = itemsToInsert.map((item, idx) => ({
      invoice_id: invoiceId,
      organization_id: organizationId,
      position: startPos + idx,
      product_name: item.product_name ?? "",
      supplier_sku: item.supplier_sku ?? null,
      brand: item.brand ?? null,
      quantity: item.quantity,
      purchase_currency: "USD",
      vat_rate: item.vat_rate ?? null,
      version: 1,
    }));

    const { data: createdItems, error: iiErr } = await supabase
      .from("invoice_items")
      .insert(iiRows)
      .select("id, invoice_id");
    if (iiErr) throw iiErr;

    if (createdItems && createdItems.length > 0) {
      // 5. Insert coverage rows (1:1 ratio=1) — pair each new invoice_item with
      //    its source quote_item. Upsert with ON CONFLICT DO NOTHING to make
      //    re-assignment idempotent (no duplicate coverage rows).
      const coverageRows = createdItems.map((created, idx) => ({
        invoice_item_id: created.id,
        quote_item_id: itemsToInsert[idx].id,
        ratio: 1,
      }));

      const { error: covErr } = await supabase
        .from("invoice_item_coverage")
        .upsert(coverageRows, {
          onConflict: "invoice_item_id,quote_item_id",
          ignoreDuplicates: true,
        });
      if (covErr) throw covErr;
    }
  }

  // 6. Update composition pointer — every assigned quote_item now points at
  //    this invoice for calc purposes. Non-destructive: coverage rows in
  //    other invoices are retained; only the pointer moves. Includes the
  //    already-covered quote_items — re-pointing them is the whole purpose
  //    of idempotent re-assignment.
  const { error: ptrErr } = await supabase
    .from("quote_items")
    .update({ composition_selected_invoice_id: invoiceId })
    .in("id", itemIds);
  if (ptrErr) throw ptrErr;
}

/**
 * Phase 5c Task 12 — split an invoice_item that's currently 1:1 covered by a
 * single quote_item into N ≥ 2 invoice_items, each with its own ratio. The
 * operation is local to one invoice: coverage in other invoices for the same
 * quote_item is untouched.
 *
 * Sequence (no DB transaction in Supabase REST client, so we fail-forward
 * with explicit rollback on error — the DELETE of the source invoice_item
 * cascades to its coverage row via ON DELETE CASCADE; INSERTing children
 * afterward keeps the window small):
 *
 *   1. Find the source invoice_item via coverage where invoice_id matches
 *      and quote_item_id = sourceQuoteItemId. There must be exactly one
 *      (1:1 coverage precondition); otherwise refuse the split.
 *   2. Compute source quote_item.quantity for ratio → quantity math.
 *   3. Read invoice metadata (organization_id, purchase_currency) for the
 *      new child rows.
 *   4. DELETE source invoice_item — cascades to its coverage row.
 *   5. INSERT N child invoice_items with computed quantities.
 *   6. INSERT N coverage rows (child_ii, sourceQuoteItemId, ratio).
 *
 * If step 5 or 6 fails, the caller sees an error — the source invoice_item
 * is already gone. Manual recovery via admin UI or DB edit; we log the
 * failure loudly via `throw`.
 */
export interface SplitChildInput {
  product_name: string;
  supplier_sku: string | null;
  brand: string | null;
  quantity_ratio: number;
  purchase_price_original: number;
  purchase_currency: string;
  weight_in_kg: number | null;
  customs_code: string | null;
}

export async function splitInvoiceItem(
  invoiceId: string,
  sourceQuoteItemId: string,
  children: SplitChildInput[]
) {
  if (children.length < 2) {
    throw new Error("Split requires at least 2 children");
  }
  for (const c of children) {
    if (!Number.isFinite(c.quantity_ratio) || c.quantity_ratio <= 0) {
      throw new Error("Each child must have quantity_ratio > 0");
    }
  }

  const supabase = createClient();

  // 1. Find source invoice_item — the one covering sourceQuoteItemId in
  //    the target invoice.
  const { data: coverageRows, error: covErr } = await supabase
    .from("invoice_item_coverage")
    .select("invoice_item_id, ratio, invoice_items!inner(id, invoice_id)")
    .eq("quote_item_id", sourceQuoteItemId);
  if (covErr) throw covErr;

  const sourceCoverage = (
    (coverageRows ?? []) as unknown as Array<{
      invoice_item_id: string;
      ratio: number;
      invoice_items: { id: string; invoice_id: string };
    }>
  ).filter((r) => r.invoice_items?.invoice_id === invoiceId);

  if (sourceCoverage.length === 0) {
    throw new Error("Исходная позиция не покрыта в этом КП");
  }
  if (sourceCoverage.length > 1) {
    throw new Error(
      "Нельзя разделить позицию, уже участвующую в разделении"
    );
  }
  const sourceInvoiceItemId = sourceCoverage[0].invoice_item_id;

  // 2. Source quote_item.quantity for ratio math.
  const { data: sourceQi, error: qiErr } = await supabase
    .from("quote_items")
    .select("quantity")
    .eq("id", sourceQuoteItemId)
    .single();
  if (qiErr) throw qiErr;
  const sourceQuantity = Number(sourceQi.quantity);
  if (!Number.isFinite(sourceQuantity) || sourceQuantity <= 0) {
    throw new Error("Некорректное количество исходной позиции");
  }

  // 3. Invoice metadata — organization_id (sourced via quote) + next
  //    position anchor. `kvota.invoices` has no organization_id column; it
  //    lives on kvota.quotes and is inherited through quote_id.
  const organizationId = await getInvoiceOrganizationId(supabase, invoiceId);

  const { data: posRow } = await supabase
    .from("invoice_items")
    .select("position")
    .eq("invoice_id", invoiceId)
    .order("position", { ascending: false })
    .limit(1);
  const startPos =
    (Array.isArray(posRow) && posRow.length > 0
      ? posRow[0].position
      : 0) + 1;

  // 4. DELETE source invoice_item — cascades to coverage row via
  //    ON DELETE CASCADE (migration 282).
  const { error: delErr } = await supabase
    .from("invoice_items")
    .delete()
    .eq("id", sourceInvoiceItemId);
  if (delErr) throw delErr;

  // 5. INSERT N child invoice_items.
  const iiRows = children.map((c, idx) => ({
    invoice_id: invoiceId,
    organization_id: organizationId,
    position: startPos + idx,
    product_name: c.product_name,
    supplier_sku: c.supplier_sku,
    brand: c.brand,
    quantity: sourceQuantity * c.quantity_ratio,
    purchase_price_original: c.purchase_price_original,
    purchase_currency: c.purchase_currency,
    weight_in_kg: c.weight_in_kg,
    customs_code: c.customs_code,
    version: 1,
  }));

  const { data: created, error: iiErr } = await supabase
    .from("invoice_items")
    .insert(iiRows)
    .select("id");
  if (iiErr) throw iiErr;
  if (!created || created.length !== children.length) {
    throw new Error("Не удалось создать новые позиции");
  }

  // 6. INSERT N coverage rows, all pointing to sourceQuoteItemId.
  const covInsert = created.map((row, idx) => ({
    invoice_item_id: row.id,
    quote_item_id: sourceQuoteItemId,
    ratio: children[idx].quantity_ratio,
  }));

  const { error: covInsertErr } = await supabase
    .from("invoice_item_coverage")
    .insert(covInsert);
  if (covInsertErr) throw covInsertErr;
}

/**
 * Phase 5c Task 13 — merge N ≥ 2 quote_items (each currently 1:1 covered in
 * THIS invoice) into a single merged invoice_item with N coverage rows
 * (all ratio=1). The merge is local to the given invoice — coverage in
 * other invoices for the same quote_items is untouched.
 *
 * Validates chain-merge prevention: each source quote_item must have
 * exactly one covering invoice_item in this invoice with ratio=1, and that
 * covering invoice_item must cover only this one quote_item. If any fail
 * the check, the operation refuses before mutating.
 *
 * Sequence (no Supabase transaction; fail-forward with hard errors):
 *   1. Load coverage for sourceQuoteItemIds; verify all are 1:1 in this
 *      invoice.
 *   2. Read invoice metadata for organization_id + next position anchor.
 *   3. DELETE the N source invoice_items — cascades to their coverage rows.
 *   4. INSERT 1 merged invoice_item.
 *   5. INSERT N coverage rows (merged_invoice_item_id, source_qi_id_i,
 *      ratio=1).
 */
export interface MergeMergedInput {
  product_name: string;
  supplier_sku: string | null;
  brand: string | null;
  quantity: number;
  purchase_price_original: number;
  purchase_currency: string;
  weight_in_kg: number | null;
  customs_code: string | null;
}

export async function mergeInvoiceItems(
  invoiceId: string,
  sourceQuoteItemIds: string[],
  merged: MergeMergedInput
) {
  if (sourceQuoteItemIds.length < 2) {
    throw new Error("Merge requires at least 2 source quote_items");
  }
  if (!Number.isFinite(merged.quantity) || merged.quantity <= 0) {
    throw new Error("Merged quantity must be > 0");
  }

  const supabase = createClient();

  // 1. Load all coverage rows for the selected quote_items. For each, the
  //    one in this invoice must be 1:1 (ratio=1, not part of any split).
  const { data: coverageRows, error: covErr } = await supabase
    .from("invoice_item_coverage")
    .select(
      "invoice_item_id, quote_item_id, ratio, invoice_items!inner(id, invoice_id)"
    )
    .in("quote_item_id", sourceQuoteItemIds);
  if (covErr) throw covErr;

  type CovRow = {
    invoice_item_id: string;
    quote_item_id: string;
    ratio: number;
    invoice_items: { id: string; invoice_id: string };
  };
  const allRows = (coverageRows ?? []) as unknown as CovRow[];

  // First pass: determine candidate covering invoice_item ids (the one per
  // source qi that lives in THIS invoice with ratio=1). Collect them so we
  // can batch-fetch all their coverage rows in a single query — avoiding the
  // per-qi N+1 issue of calling the DB once per source.
  const candidateIiByQi = new Map<string, string>();
  for (const qiId of sourceQuoteItemIds) {
    const rowsInThisInvoice = allRows.filter(
      (r) =>
        r.quote_item_id === qiId && r.invoice_items?.invoice_id === invoiceId
    );
    if (rowsInThisInvoice.length === 0) {
      throw new Error("Выбранная позиция не покрыта в этом КП");
    }
    if (rowsInThisInvoice.length > 1) {
      throw new Error(
        "Нельзя объединить позицию, уже участвующую в разделении"
      );
    }
    const only = rowsInThisInvoice[0];
    if (Number(only.ratio) !== 1) {
      throw new Error(
        "Нельзя объединить позицию, уже участвующую в разделении/объединении"
      );
    }
    candidateIiByQi.set(qiId, only.invoice_item_id);
  }

  // Batch-fetch: for each candidate invoice_item, read ALL coverage rows at
  // once via WHERE invoice_item_id IN (...). One query regardless of how
  // many quote_items are being merged.
  const candidateIiIds = Array.from(new Set(candidateIiByQi.values()));
  const { data: allCoverageForCandidates, error: batchCovErr } = await supabase
    .from("invoice_item_coverage")
    .select("invoice_item_id, quote_item_id")
    .in("invoice_item_id", candidateIiIds);
  if (batchCovErr) throw batchCovErr;

  // Group returned rows by invoice_item_id so we can do O(1) lookups below.
  const coverageByIi = new Map<string, number>();
  for (const row of allCoverageForCandidates ?? []) {
    coverageByIi.set(
      row.invoice_item_id,
      (coverageByIi.get(row.invoice_item_id) ?? 0) + 1
    );
  }

  // Second pass: validate that each candidate invoice_item covers ONLY its
  // source quote_item (not already a merge). This uses in-memory counts
  // computed from the single batch query above.
  const sourceInvoiceItemIds = new Set<string>();
  for (const [, iiId] of candidateIiByQi) {
    const count = coverageByIi.get(iiId) ?? 0;
    if (count > 1) {
      throw new Error(
        "Нельзя объединить позицию, уже участвующую в объединении"
      );
    }
    sourceInvoiceItemIds.add(iiId);
  }

  if (sourceInvoiceItemIds.size < 2) {
    throw new Error(
      "Нужно выбрать минимум 2 разных позиции с 1:1 покрытием"
    );
  }

  // 2. Invoice metadata — organization_id (sourced via quote) + next
  //    position anchor. `kvota.invoices` has no organization_id column; it
  //    lives on kvota.quotes and is inherited through quote_id.
  const organizationId = await getInvoiceOrganizationId(supabase, invoiceId);

  const { data: posRow } = await supabase
    .from("invoice_items")
    .select("position")
    .eq("invoice_id", invoiceId)
    .order("position", { ascending: false })
    .limit(1);
  const nextPos =
    (Array.isArray(posRow) && posRow.length > 0
      ? posRow[0].position
      : 0) + 1;

  // 3. DELETE N source invoice_items — cascades to coverage rows.
  const { error: delErr } = await supabase
    .from("invoice_items")
    .delete()
    .in("id", Array.from(sourceInvoiceItemIds));
  if (delErr) throw delErr;

  // 4. INSERT 1 merged invoice_item.
  const { data: createdRow, error: insErr } = await supabase
    .from("invoice_items")
    .insert({
      invoice_id: invoiceId,
      organization_id: organizationId,
      position: nextPos,
      product_name: merged.product_name,
      supplier_sku: merged.supplier_sku,
      brand: merged.brand,
      quantity: merged.quantity,
      purchase_price_original: merged.purchase_price_original,
      purchase_currency: merged.purchase_currency,
      weight_in_kg: merged.weight_in_kg,
      customs_code: merged.customs_code,
      version: 1,
    })
    .select("id")
    .single();
  if (insErr) throw insErr;
  const mergedIiId = createdRow.id;

  // 5. INSERT N coverage rows pointing to the merged invoice_item, each
  //    with ratio=1 (definition of merge: N:1 with ratio = 1 per row).
  const covInsert = sourceQuoteItemIds.map((qiId) => ({
    invoice_item_id: mergedIiId,
    quote_item_id: qiId,
    ratio: 1,
  }));

  const { error: covInsertErr } = await supabase
    .from("invoice_item_coverage")
    .insert(covInsert);
  if (covInsertErr) throw covInsertErr;
}

/**
 * Phase 5d Group 5 Appendix — remove one supplier-side position from its KP.
 *
 * Input is an invoice_items.id (post-Task-14 rowId on procurement-handsontable).
 * Deletes the invoice_item row (cascades invoice_item_coverage via
 * ON DELETE CASCADE from migration 282), then resets
 * quote_items.composition_selected_invoice_id for any quote_item whose last
 * coverage in that invoice just disappeared.
 *
 * Sequence:
 *   1. Read coverage for this invoice_item to discover the covered
 *      quote_items + the containing invoice.
 *   2. DELETE invoice_item (cascades coverage rows).
 *   3. For each previously-covered quote_item, re-check coverage in the
 *      same invoice. If none remains, clear composition_selected_invoice_id
 *      for that quote_item (only when it currently equals this invoice).
 *
 * Split/merge safety: when a quote_item was covered by multiple invoice_items
 * in the same invoice (split), removing one leaves the pointer alone. When
 * an invoice_item covers multiple quote_items (merge), each is checked
 * individually.
 *
 * Does NOT touch coverage rows in other invoices (non-destructive to
 * alternatives). Corresponds to the trash-icon "убрать из КП" action in
 * procurement-handsontable.
 */
export async function unassignInvoiceItem(invoiceItemId: string) {
  const supabase = createClient();

  // 1. Fetch coverage rows for this invoice_item to determine which
  //    quote_items we may need to reset the composition pointer for, and
  //    which invoice to check remaining coverage in.
  const { data: coverageRows, error: covErr } = await supabase
    .from("invoice_item_coverage")
    .select("invoice_item_id, quote_item_id, invoice_items!inner(invoice_id)")
    .eq("invoice_item_id", invoiceItemId);
  if (covErr) throw covErr;

  type CovRow = {
    invoice_item_id: string;
    quote_item_id: string;
    invoice_items: { invoice_id: string };
  };
  const coveredRows = (coverageRows ?? []) as unknown as CovRow[];
  const coveredQiIds = Array.from(
    new Set(coveredRows.map((r) => r.quote_item_id))
  );
  const invoiceId = coveredRows[0]?.invoice_items?.invoice_id ?? null;

  // 2. DELETE invoice_item — cascades to coverage rows via ON DELETE CASCADE.
  const { error: delErr } = await supabase
    .from("invoice_items")
    .delete()
    .eq("id", invoiceItemId);
  if (delErr) throw delErr;

  if (coveredQiIds.length === 0 || !invoiceId) {
    // Orphan invoice_item with no coverage (e.g. manual addition) or we
    // could not determine the invoice — nothing else to reset.
    return;
  }

  // 3. For each previously-covered quote_item, re-check remaining coverage
  //    in the same invoice. Clear the composition pointer for those with no
  //    coverage left there.
  const { data: remainingCov, error: remErr } = await supabase
    .from("invoice_item_coverage")
    .select("quote_item_id, invoice_items!inner(invoice_id)")
    .in("quote_item_id", coveredQiIds);
  if (remErr) throw remErr;

  const qiStillCoveredInInvoice = new Set<string>(
    (
      (remainingCov ?? []) as unknown as Array<{
        quote_item_id: string;
        invoice_items: { invoice_id: string };
      }>
    )
      .filter((r) => r.invoice_items?.invoice_id === invoiceId)
      .map((r) => r.quote_item_id)
  );

  const qiIdsToClear = coveredQiIds.filter(
    (qiId) => !qiStillCoveredInInvoice.has(qiId)
  );

  if (qiIdsToClear.length > 0) {
    const { error: ptrErr } = await supabase
      .from("quote_items")
      .update({ composition_selected_invoice_id: null })
      .in("id", qiIdsToClear);
    if (ptrErr) throw ptrErr;
  }
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

  // Clear composition pointer for any quote_items that had this invoice
  // selected — the delete below cascades to invoice_items → coverage, but
  // quote_items.composition_selected_invoice_id is a plain FK without ON
  // DELETE CASCADE so we must null it explicitly.
  await supabase
    .from("quote_items")
    .update({ composition_selected_invoice_id: null })
    .eq("composition_selected_invoice_id", invoiceId);

  // invoice_items + invoice_item_coverage cascade from this DELETE via
  // ON DELETE CASCADE (migrations 281/282).
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

// ---------------------------------------------------------------------------
// Soft-delete + Restore (admin-only) — hit the Python API which cascades
// across quotes/specifications/deals in one transaction. UI gates (DeleteMenu,
// Trash page) are defense-in-depth; the Python endpoint re-validates admin
// role. Same shared result shape for both.
// ---------------------------------------------------------------------------

export interface SoftDeleteResult {
  quote_affected: number;
  spec_affected: number;
  deal_affected: number;
}

export async function softDeleteQuote(
  quoteId: string
): Promise<SoftDeleteResult> {
  return _callLifecycleAction(quoteId, "soft-delete", "Soft-delete failed");
}

export async function restoreQuote(
  quoteId: string
): Promise<SoftDeleteResult> {
  return _callLifecycleAction(quoteId, "restore", "Restore failed");
}

async function _callLifecycleAction(
  quoteId: string,
  action: "soft-delete" | "restore",
  genericError: string
): Promise<SoftDeleteResult> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const res = await fetch(`/api/quotes/${quoteId}/${action}`, {
    method: "POST",
    headers: {
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
    },
  });

  const json = await res.json().catch(() => null);
  if (!res.ok || !json?.success) {
    throw new Error(json?.error?.message ?? genericError);
  }
  return json.data as SoftDeleteResult;
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
