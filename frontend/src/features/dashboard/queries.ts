import { createAdminClient } from "@/shared/lib/supabase/server";

export interface PeriodRange {
  from: string;
  to: string;
}

export function getPeriodRange(period: string): PeriodRange {
  const now = new Date();
  const to = now.toISOString();
  let from: Date;

  switch (period) {
    case "week":
      from = new Date(now);
      from.setDate(from.getDate() - 7);
      break;
    case "quarter":
      from = new Date(now);
      from.setMonth(from.getMonth() - 3);
      break;
    case "year":
      from = new Date(now.getFullYear(), 0, 1);
      break;
    case "month":
    default:
      from = new Date(now.getFullYear(), now.getMonth(), 1);
      break;
  }

  return { from: from.toISOString(), to };
}

export interface QuotesMetrics {
  created: number;
  processed: number;
  processedPct: number;
  medianProcessingDays: number | null;
}

export interface ProposalsMetrics {
  count: number;
  totalUsd: number;
  profitUsd: number;
}

export interface DealsMetrics {
  count: number;
  totalAmount: number;
  profitUsd: number;
  conversionPct: number;
}

export async function fetchQuotesMetrics(
  orgId: string,
  range: PeriodRange
): Promise<QuotesMetrics> {
  const admin = createAdminClient();

  // Per-invoice procurement model (post PR #74): closure lives on
  // ``invoices.procurement_completed_at``. A quote counts as "processed"
  // when at least one of its invoices is procurement-complete; the
  // duration metric uses the LATEST invoice closure (≈ when the whole
  // quote left procurement).
  const [createdRes, completedInvoicesRes] = await Promise.all([
    admin
      .from("quotes")
      .select("id", { count: "exact", head: true })
      .eq("organization_id", orgId)
      .is("deleted_at", null)
      .gte("created_at", range.from)
      .lte("created_at", range.to),
    admin
      .from("invoices")
      .select(
        "quote_id, procurement_completed_at, quotes!quote_id!inner(organization_id, created_at, deleted_at)"
      )
      .eq("quotes.organization_id", orgId)
      .is("quotes.deleted_at", null)
      .not("procurement_completed_at", "is", null)
      .gte("procurement_completed_at", range.from)
      .lte("procurement_completed_at", range.to),
  ]);

  const created = createdRes.count ?? 0;

  // Group invoice closures by quote, keep the latest closure per quote.
  type InvoiceRow = {
    quote_id: string;
    procurement_completed_at: string;
    quotes: { created_at: string | null } | null;
  };
  const completedInvoices =
    (completedInvoicesRes.data ?? []) as unknown as InvoiceRow[];
  const latestByQuote = new Map<string, { createdAt: string; completedAt: string }>();
  for (const inv of completedInvoices) {
    const completedAt = inv.procurement_completed_at;
    const createdAt = inv.quotes?.created_at;
    if (!completedAt || !createdAt) continue;
    const prev = latestByQuote.get(inv.quote_id);
    if (!prev || prev.completedAt < completedAt) {
      latestByQuote.set(inv.quote_id, { createdAt, completedAt });
    }
  }

  const processed = latestByQuote.size;
  const processedPct = created > 0 ? Math.round((processed / created) * 100) : 0;

  let medianProcessingDays: number | null = null;
  if (latestByQuote.size > 0) {
    const durations = Array.from(latestByQuote.values())
      .map(({ createdAt, completedAt }) => {
        const start = new Date(createdAt).getTime();
        const end = new Date(completedAt).getTime();
        return (end - start) / (1000 * 60 * 60 * 24);
      })
      .sort((a, b) => a - b);

    const mid = Math.floor(durations.length / 2);
    medianProcessingDays =
      durations.length % 2 === 0
        ? (durations[mid - 1] + durations[mid]) / 2
        : durations[mid];
    medianProcessingDays = Math.round(medianProcessingDays * 10) / 10;
  }

  return { created, processed, processedPct, medianProcessingDays };
}

const NEGOTIATION_STATUSES = [
  "sent_to_client",
  "approved",
  "accepted",
  "pending_spec_control",
  "spec_signed",
];

export async function fetchProposalsMetrics(
  orgId: string,
  range: PeriodRange
): Promise<ProposalsMetrics> {
  const admin = createAdminClient();

  const { data: proposalsData } = await admin
    .from("quotes")
    .select("total_amount_usd, total_profit_usd")
    .eq("organization_id", orgId)
    .is("deleted_at", null)
    .in("workflow_status", NEGOTIATION_STATUSES)
    .gte("created_at", range.from)
    .lte("created_at", range.to);

  const rows = proposalsData ?? [];
  const count = rows.length;
  const totalUsd = rows.reduce((sum, r) => sum + (r.total_amount_usd ?? 0), 0);
  const profitUsd = rows.reduce((sum, r) => sum + (r.total_profit_usd ?? 0), 0);

  return { count, totalUsd, profitUsd };
}

export async function fetchDealsMetrics(
  orgId: string,
  range: PeriodRange
): Promise<DealsMetrics> {
  const admin = createAdminClient();

  const { data: deals } = await admin
    .from("deals")
    .select("id, total_amount, quote_id")
    .eq("organization_id", orgId)
    .is("deleted_at", null)
    .gte("created_at", range.from)
    .lte("created_at", range.to);

  const dealsRows = deals ?? [];
  const count = dealsRows.length;
  const totalAmount = dealsRows.reduce((sum, d) => sum + (d.total_amount ?? 0), 0);

  // Get profit from linked quotes + cohort conversion
  const quoteIds = dealsRows.map((d) => d.quote_id).filter(Boolean);

  const [profitRes, cohortRes] = await Promise.all([
    quoteIds.length > 0
      ? admin.from("quotes").select("total_profit_usd").in("id", quoteIds).is("deleted_at", null)
      : Promise.resolve({ data: [] }),
    // Cohort: how many quotes created in this period ever became deals?
    admin
      .from("quotes")
      .select("id", { count: "exact", head: true })
      .eq("organization_id", orgId)
      .is("deleted_at", null)
      .gte("created_at", range.from)
      .lte("created_at", range.to),
  ]);

  const profitUsd = (profitRes.data ?? []).reduce(
    (sum: number, q: { total_profit_usd: number | null }) => sum + (q.total_profit_usd ?? 0), 0
  );
  const cohortQuotes = cohortRes.count ?? 0;
  // count = deals whose quotes were created in this period (cohort deals)
  const conversionPct =
    cohortQuotes > 0 ? Math.round((count / cohortQuotes) * 100) : 0;

  return { count, totalAmount, profitUsd, conversionPct };
}
