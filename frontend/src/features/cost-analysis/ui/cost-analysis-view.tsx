import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { getStatusLabel } from "@/entities/quote";
import { SummaryCards } from "./summary-cards";
import { WaterfallTable } from "./waterfall-table";
import { NotCalculated } from "./not-calculated";
import type { CostAnalysisView as CostAnalysisViewData } from "../types";

interface CostAnalysisViewProps {
  data: CostAnalysisViewData;
}

/**
 * Server-rendered cost-analysis page body. Shows header + summary cards +
 * P&L waterfall when calculation data exists; otherwise shows the empty
 * state prompting the user to run a calculation.
 */
export function CostAnalysisView({ data }: CostAnalysisViewProps) {
  const { quote, has_calculation, totals, logistics_breakdown, derived } =
    data;

  const backHref = `/quotes/${quote.id}`;

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Breadcrumb + header */}
      <div className="flex flex-col gap-2">
        <Link
          href={backHref}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-3.5 h-3.5" aria-hidden />
          <span>Назад к КП</span>
        </Link>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-semibold">
            Кост-анализ — {quote.idn_quote}
          </h1>
          <Badge variant="secondary">{getStatusLabel(quote.workflow_status)}</Badge>
        </div>
        {(quote.title || quote.customer_name) && (
          <p className="text-sm text-muted-foreground">
            {quote.title}
            {quote.title && quote.customer_name ? " · " : ""}
            {quote.customer_name}
          </p>
        )}
      </div>

      {has_calculation ? (
        <>
          <SummaryCards
            totals={totals}
            derived={derived}
            currency={quote.currency}
          />
          <section className="flex flex-col gap-3">
            <h2 className="text-base font-semibold">
              P&amp;L Waterfall — Кост-анализ
            </h2>
            <div className="rounded-xl bg-card ring-1 ring-foreground/10 p-4">
              <WaterfallTable
                totals={totals}
                logistics={logistics_breakdown}
                derived={derived}
                currency={quote.currency}
              />
            </div>
          </section>
        </>
      ) : (
        <NotCalculated />
      )}
    </div>
  );
}
