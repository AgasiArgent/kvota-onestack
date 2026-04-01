import { createAdminClient } from "@/shared/lib/supabase/server";
import type {
  DealListItem,
  DealSummary,
  DealsFilterParams,
  DealsListResult,
  PaymentRecord,
  PaymentsFilterParams,
  PaymentTotals,
  PaymentsListResult,
  SupplierInvoiceItem,
  SupplierInvoicesFilterParams,
  CurrencyTotal,
  SupplierInvoicesListResult,
} from "./types";
import { formatStageLabel } from "./types";

const DEFAULT_PAGE_SIZE = 20;

export async function fetchDeals(
  orgId: string,
  filters: DealsFilterParams
): Promise<DealsListResult> {
  const admin = createAdminClient();
  const page = filters.page ?? 1;
  const pageSize = filters.pageSize ?? DEFAULT_PAGE_SIZE;
  const offset = (page - 1) * pageSize;

  // Step 1: Build summary (all deals, ignoring pagination)
  const { data: allDeals } = await admin
    .from("deals")
    .select("id, status, quote_id")
    .eq("organization_id", orgId);

  const dealRows = allDeals ?? [];

  // Batch-fetch quote totals for summary
  const allQuoteIds = Array.from(
    new Set(
      dealRows
        .map((d) => d.quote_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: summaryQuotes } = allQuoteIds.length > 0
    ? await admin
        .from("quotes")
        .select("id, total_amount_usd")
        .in("id", allQuoteIds)
    : { data: [] as { id: string; total_amount_usd: number | null }[] };

  const summaryQuoteMap = new Map(
    (summaryQuotes ?? []).map((q) => [q.id, q.total_amount_usd ?? 0])
  );

  const summary: DealSummary = {
    active_count: 0,
    active_total: 0,
    completed_count: 0,
    completed_total: 0,
    cancelled_count: 0,
    cancelled_total: 0,
    total_count: dealRows.length,
    total_amount: 0,
  };

  for (const d of dealRows) {
    const amount = d.quote_id ? summaryQuoteMap.get(d.quote_id) ?? 0 : 0;
    summary.total_amount += amount;
    if (d.status === "active") {
      summary.active_count++;
      summary.active_total += amount;
    } else if (d.status === "completed") {
      summary.completed_count++;
      summary.completed_total += amount;
    } else if (d.status === "cancelled") {
      summary.cancelled_count++;
      summary.cancelled_total += amount;
    }
  }

  // Step 2: Fetch paginated deals
  let query = admin
    .from("deals")
    .select("id, deal_number, specification_id, quote_id, status, created_at", {
      count: "exact",
    })
    .eq("organization_id", orgId)
    .order("created_at", { ascending: false });

  if (filters.status) {
    query = query.eq("status", filters.status);
  }

  query = query.range(offset, offset + pageSize - 1);

  const { data: rows, count, error } = await query;
  if (error) throw error;

  const pageRows = rows ?? [];
  if (pageRows.length === 0) {
    return { data: [], summary, total: count ?? 0, page, pageSize };
  }

  // Step 3: Batch-resolve specifications
  const specIds = Array.from(
    new Set(
      pageRows
        .map((r) => r.specification_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: specs } = specIds.length > 0
    ? await admin
        .from("specifications")
        .select(
          "id, specification_number, sign_date, client_payment_terms, payment_deferral_days, delivery_period_days"
        )
        .in("id", specIds)
    : { data: [] as { id: string; specification_number: string | null; sign_date: string | null; client_payment_terms: string | null; payment_deferral_days: number | null; delivery_period_days: number | null }[] };

  const specMap = new Map(
    (specs ?? []).map((s) => [s.id, s])
  );

  // Step 4: Batch-resolve quotes (for totals + customer_id)
  const quoteIds = Array.from(
    new Set(
      pageRows
        .map((r) => r.quote_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: quotes } = quoteIds.length > 0
    ? await admin
        .from("quotes")
        .select("id, idn_quote, total_amount_usd, total_profit_usd, customer_id")
        .in("id", quoteIds)
    : { data: [] as { id: string; idn_quote: string; total_amount_usd: number | null; total_profit_usd: number | null; customer_id: string | null }[] };

  const quoteMap = new Map(
    (quotes ?? []).map((q) => [q.id, q])
  );

  // Step 5: Batch-resolve customers
  const customerIds = Array.from(
    new Set(
      (quotes ?? [])
        .map((q) => q.customer_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: customers } = customerIds.length > 0
    ? await admin.from("customers").select("id, name").in("id", customerIds)
    : { data: [] as { id: string; name: string }[] };

  const customerMap = new Map(
    (customers ?? []).map((c) => [c.id, c.name])
  );

  // Step 6: Batch-resolve payment aggregates from plan_fact_items
  // plan_fact_items has no is_income — we need category info to determine income/expense
  const dealIds = pageRows.map((r) => r.id);

  const { data: paymentItems } = await admin
    .from("plan_fact_items")
    .select("deal_id, actual_amount, category_id")
    .in("deal_id", dealIds);

  // Fetch all relevant categories to get is_income
  const paymentCategoryIds = Array.from(
    new Set(
      (paymentItems ?? [])
        .map((p) => p.category_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: paymentCategories } = paymentCategoryIds.length > 0
    ? await admin
        .from("plan_fact_categories")
        .select("id, is_income")
        .in("id", paymentCategoryIds)
    : { data: [] as { id: string; is_income: boolean }[] };

  const incomeCategoryIds = new Set(
    (paymentCategories ?? []).filter((c) => c.is_income).map((c) => c.id)
  );

  // Aggregate total paid per deal (sum of actual_amount where category is_income=true)
  const paidByDeal = new Map<string, number>();
  for (const p of paymentItems ?? []) {
    if (incomeCategoryIds.has(p.category_id) && p.actual_amount) {
      paidByDeal.set(
        p.deal_id,
        (paidByDeal.get(p.deal_id) ?? 0) + Number(p.actual_amount)
      );
    }
  }

  // Step 7: Assemble results
  const items: DealListItem[] = pageRows.map((row) => {
    const spec = row.specification_id ? specMap.get(row.specification_id) : undefined;
    const quote = row.quote_id ? quoteMap.get(row.quote_id) : undefined;
    const customerName = quote?.customer_id
      ? customerMap.get(quote.customer_id) ?? null
      : null;
    const totalAmountUsd = quote?.total_amount_usd ?? null;
    const totalPaid = paidByDeal.get(row.id) ?? 0;
    const remaining = totalAmountUsd !== null ? totalAmountUsd - totalPaid : null;

    // Calculate deadline from sign_date + delivery_period_days + payment_deferral_days
    let deadline: string | null = null;
    if (spec?.sign_date && spec?.delivery_period_days) {
      const d = new Date(spec.sign_date);
      d.setDate(d.getDate() + spec.delivery_period_days + (spec.payment_deferral_days ?? 0));
      deadline = d.toISOString().split("T")[0];
    }

    return {
      id: row.id,
      deal_number: row.deal_number,
      spec_number: spec?.specification_number ?? null,
      quote_idn: quote?.idn_quote ?? null,
      customer_name: customerName,
      total_amount_usd: totalAmountUsd,
      profit_usd: quote?.total_profit_usd ?? null,
      sign_date: spec?.sign_date ?? null,
      status: (row.status ?? "active") as "active" | "completed" | "cancelled",
      payment_terms: spec?.client_payment_terms ?? null,
      advance_percent: null,
      total_paid_usd: totalPaid > 0 ? totalPaid : null,
      remaining_usd: remaining,
      deadline,
    };
  });

  return { data: items, summary, total: count ?? 0, page, pageSize };
}

export async function fetchPayments(
  orgId: string,
  filters: PaymentsFilterParams
): Promise<PaymentsListResult> {
  const admin = createAdminClient();
  const page = filters.page ?? 1;
  const pageSize = filters.pageSize ?? DEFAULT_PAGE_SIZE;
  const offset = (page - 1) * pageSize;

  // plan_fact_items has no organization_id — filter via deals
  // Step 1: Get deal IDs for this org
  const { data: orgDeals } = await admin
    .from("deals")
    .select("id, deal_number, quote_id")
    .eq("organization_id", orgId);

  const orgDealIds = (orgDeals ?? []).map((d) => d.id);
  if (orgDealIds.length === 0) {
    return {
      data: [],
      totals: { planned_income: 0, actual_income: 0, planned_expense: 0, actual_expense: 0, balance: 0 },
      total: 0,
      page,
      pageSize,
    };
  }

  const dealMap = new Map(
    (orgDeals ?? []).map((d) => [d.id, d])
  );

  // Step 2: Fetch all plan_fact_items for these deals
  let query = admin
    .from("plan_fact_items")
    .select("id, deal_id, description, planned_amount, planned_date, planned_currency, actual_amount, actual_currency, actual_date, category_id")
    .in("deal_id", orgDealIds)
    .order("planned_date", { ascending: false, nullsFirst: false });

  // Apply date range filters
  if (filters.date_from) {
    query = query.gte("planned_date", filters.date_from);
  }
  if (filters.date_to) {
    query = query.lte("planned_date", filters.date_to);
  }

  const { data: allRows, error } = await query;
  if (error) throw error;

  const rawRows = allRows ?? [];

  // Step 3: Batch-resolve categories (contains is_income and code)
  const categoryIds = Array.from(
    new Set(
      rawRows
        .map((r) => r.category_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: categories } = categoryIds.length > 0
    ? await admin
        .from("plan_fact_categories")
        .select("id, name, code, is_income")
        .in("id", categoryIds)
    : { data: [] as { id: string; name: string; code: string; is_income: boolean }[] };

  const categoryMap = new Map(
    (categories ?? []).map((c) => [c.id, c])
  );

  // Step 4: Batch-resolve customer names via quotes
  const quoteIds = Array.from(
    new Set(
      (orgDeals ?? [])
        .map((d) => d.quote_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: quotes } = quoteIds.length > 0
    ? await admin
        .from("quotes")
        .select("id, customer_id")
        .in("id", quoteIds)
    : { data: [] as { id: string; customer_id: string | null }[] };

  const quoteMap = new Map(
    (quotes ?? []).map((q) => [q.id, q])
  );

  const customerIds = Array.from(
    new Set(
      (quotes ?? [])
        .map((q) => q.customer_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: customers } = customerIds.length > 0
    ? await admin.from("customers").select("id, name").in("id", customerIds)
    : { data: [] as { id: string; name: string }[] };

  const customerMap = new Map(
    (customers ?? []).map((c) => [c.id, c.name])
  );

  // Step 5: Build records with derived status
  const today = new Date().toISOString().split("T")[0];

  type EnrichedRecord = PaymentRecord & { derived_status: string };

  const enrichedRows: EnrichedRecord[] = rawRows.map((row) => {
    const category = row.category_id ? categoryMap.get(row.category_id) : undefined;
    const deal = row.deal_id ? dealMap.get(row.deal_id) : undefined;
    const quote = deal?.quote_id ? quoteMap.get(deal.quote_id) : undefined;
    const customerName = quote?.customer_id
      ? customerMap.get(quote.customer_id) ?? null
      : null;

    const isIncome = category?.is_income ?? false;

    // Derive payment status
    let derivedStatus = "plan";
    if (row.actual_amount && row.actual_date) {
      derivedStatus = "paid";
    } else if (row.planned_date && row.planned_date < today) {
      derivedStatus = "overdue";
    }

    // Apply stage label translation to description
    const description = row.description
      ? formatStageLabel(row.description)
      : null;

    return {
      id: row.id,
      deal_id: row.deal_id ?? "",
      deal_number: deal?.deal_number ?? "",
      customer_name: customerName,
      category_id: row.category_id ?? "",
      category_name: category?.name ?? "",
      category_slug: category?.code ?? "",
      is_income: isIncome,
      description,
      planned_amount: row.planned_amount ? Number(row.planned_amount) : null,
      planned_date: row.planned_date,
      planned_currency: row.planned_currency ?? "USD",
      actual_amount: row.actual_amount ? Number(row.actual_amount) : null,
      actual_currency: row.actual_currency ?? null,
      actual_date: row.actual_date,
      derived_status: derivedStatus,
    };
  });

  // Step 6: Apply type filter (income/expense — based on category.is_income)
  let filteredRows = enrichedRows;
  if (filters.type === "income") {
    filteredRows = filteredRows.filter((r) => r.is_income);
  } else if (filters.type === "expense") {
    filteredRows = filteredRows.filter((r) => !r.is_income);
  }

  // Step 7: Apply status filter (post-query)
  if (filters.payment_status) {
    filteredRows = filteredRows.filter(
      (r) => r.derived_status === filters.payment_status
    );
  }

  // Step 8: Calculate totals (on filtered set, before pagination)
  const totals: PaymentTotals = {
    planned_income: 0,
    actual_income: 0,
    planned_expense: 0,
    actual_expense: 0,
    balance: 0,
  };

  for (const r of filteredRows) {
    if (r.is_income) {
      totals.planned_income += r.planned_amount ?? 0;
      totals.actual_income += r.actual_amount ?? 0;
    } else {
      totals.planned_expense += r.planned_amount ?? 0;
      totals.actual_expense += r.actual_amount ?? 0;
    }
  }
  totals.balance = totals.actual_income - totals.actual_expense;

  // Step 9: Paginate
  const totalFiltered = filteredRows.length;
  const paginatedRows = filteredRows.slice(offset, offset + pageSize);

  // Strip derived_status from output
  const items: PaymentRecord[] = paginatedRows.map(({ derived_status: _, ...rest }) => rest);

  return { data: items, totals, total: totalFiltered, page, pageSize };
}

export async function fetchSupplierInvoices(
  orgId: string,
  filters: SupplierInvoicesFilterParams
): Promise<SupplierInvoicesListResult> {
  const admin = createAdminClient();
  const page = filters.page ?? 1;
  const pageSize = filters.pageSize ?? DEFAULT_PAGE_SIZE;
  const offset = (page - 1) * pageSize;

  // Step 1: Fetch supplier invoices (real columns: invoice_date, total_amount)
  const query = admin
    .from("supplier_invoices")
    .select("id, invoice_number, supplier_id, invoice_date, total_amount, currency, status", {
      count: "exact",
    })
    .eq("organization_id", orgId)
    .order("invoice_date", { ascending: false, nullsFirst: false })
    .range(offset, offset + pageSize - 1);

  const { data: rows, count, error } = await query;
  if (error) throw error;

  const pageRows = rows ?? [];

  // Step 2: Fetch all invoices for currency totals (not just this page)
  const { data: allInvoices } = await admin
    .from("supplier_invoices")
    .select("total_amount, currency")
    .eq("organization_id", orgId);

  const currencyTotalsMap = new Map<string, number>();
  for (const inv of allInvoices ?? []) {
    if (inv.total_amount && inv.currency) {
      currencyTotalsMap.set(
        inv.currency,
        (currencyTotalsMap.get(inv.currency) ?? 0) + Number(inv.total_amount)
      );
    }
  }

  const currency_totals: CurrencyTotal[] = Array.from(currencyTotalsMap.entries())
    .map(([currency, total]) => ({ currency, total }))
    .sort((a, b) => a.currency.localeCompare(b.currency));

  if (pageRows.length === 0) {
    return { data: [], currency_totals, total: count ?? 0, page, pageSize };
  }

  // Step 3: Batch-resolve supplier names
  const supplierIds = Array.from(
    new Set(
      pageRows
        .map((r) => r.supplier_id)
        .filter((id): id is string => id !== null)
    )
  );

  const { data: suppliers } = supplierIds.length > 0
    ? await admin.from("suppliers").select("id, name").in("id", supplierIds)
    : { data: [] as { id: string; name: string }[] };

  const supplierMap = new Map(
    (suppliers ?? []).map((s) => [s.id, s.name])
  );

  // Step 4: Assemble (no quote_id on supplier_invoices table)
  const items: SupplierInvoiceItem[] = pageRows.map((row) => ({
    id: row.id,
    invoice_number: row.invoice_number,
    supplier_name: row.supplier_id
      ? supplierMap.get(row.supplier_id) ?? null
      : null,
    date: row.invoice_date,
    amount: row.total_amount ? Number(row.total_amount) : null,
    currency: row.currency ?? "USD",
    status: row.status ?? "pending",
    quote_idn: null, // supplier_invoices has no direct quote link
  }));

  return { data: items, currency_totals, total: count ?? 0, page, pageSize };
}
