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
  conversionPct: number;
}

export interface DealsMetrics {
  count: number;
  totalAmount: number;
  profitUsd: number;
}

export async function fetchQuotesMetrics(
  orgId: string,
  range: PeriodRange
): Promise<QuotesMetrics> {
  const admin = createAdminClient();

  const [createdRes, processedRes] = await Promise.all([
    admin
      .from("quotes")
      .select("id", { count: "exact", head: true })
      .eq("organization_id", orgId)
      .is("deleted_at", null)
      .gte("created_at", range.from)
      .lte("created_at", range.to),
    admin
      .from("quotes")
      .select("created_at, procurement_completed_at")
      .eq("organization_id", orgId)
      .is("deleted_at", null)
      .not("procurement_completed_at", "is", null)
      .gte("procurement_completed_at", range.from)
      .lte("procurement_completed_at", range.to),
  ]);

  const created = createdRes.count ?? 0;
  const processedRows = processedRes.data ?? [];
  const processed = processedRows.length;
  const processedPct = created > 0 ? Math.round((processed / created) * 100) : 0;

  let medianProcessingDays: number | null = null;
  if (processedRows.length > 0) {
    const durations = processedRows
      .filter((r) => r.created_at && r.procurement_completed_at)
      .map((r) => {
        const start = new Date(r.created_at!).getTime();
        const end = new Date(r.procurement_completed_at!).getTime();
        return (end - start) / (1000 * 60 * 60 * 24);
      })
      .sort((a, b) => a - b);

    if (durations.length > 0) {
      const mid = Math.floor(durations.length / 2);
      medianProcessingDays =
        durations.length % 2 === 0
          ? (durations[mid - 1] + durations[mid]) / 2
          : durations[mid];
      medianProcessingDays = Math.round(medianProcessingDays * 10) / 10;
    }
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

  const [proposalsRes, allQuotesRes, dealsInPeriodRes] = await Promise.all([
    admin
      .from("quotes")
      .select("total_amount_usd, total_profit_usd")
      .eq("organization_id", orgId)
      .is("deleted_at", null)
      .in("workflow_status", NEGOTIATION_STATUSES)
      .gte("created_at", range.from)
      .lte("created_at", range.to),
    admin
      .from("quotes")
      .select("id", { count: "exact", head: true })
      .eq("organization_id", orgId)
      .is("deleted_at", null)
      .gte("created_at", range.from)
      .lte("created_at", range.to),
    admin
      .from("deals")
      .select("id", { count: "exact", head: true })
      .eq("organization_id", orgId)
      .gte("created_at", range.from)
      .lte("created_at", range.to),
  ]);

  const rows = proposalsRes.data ?? [];
  const count = rows.length;
  const totalUsd = rows.reduce((sum, r) => sum + (r.total_amount_usd ?? 0), 0);
  const profitUsd = rows.reduce((sum, r) => sum + (r.total_profit_usd ?? 0), 0);

  const allQuotes = allQuotesRes.count ?? 0;
  const dealsCount = dealsInPeriodRes.count ?? 0;
  const conversionPct =
    allQuotes > 0 ? Math.round((dealsCount / allQuotes) * 100) : 0;

  return { count, totalUsd, profitUsd, conversionPct };
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
    .gte("created_at", range.from)
    .lte("created_at", range.to);

  const dealsRows = deals ?? [];
  const count = dealsRows.length;
  const totalAmount = dealsRows.reduce((sum, d) => sum + (d.total_amount ?? 0), 0);

  // Get profit from linked quotes
  const quoteIds = dealsRows.map((d) => d.quote_id).filter(Boolean);
  let profitUsd = 0;
  if (quoteIds.length > 0) {
    const { data: quotes } = await admin
      .from("quotes")
      .select("total_profit_usd")
      .in("id", quoteIds);
    profitUsd = (quotes ?? []).reduce((sum, q) => sum + (q.total_profit_usd ?? 0), 0);
  }

  return { count, totalAmount, profitUsd };
}
