import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { formatAmount, formatPercent } from "./format";
import type {
  CostAnalysisDerived,
  CostAnalysisTotals,
} from "../types";

interface SummaryCardsProps {
  totals: CostAnalysisTotals;
  derived: CostAnalysisDerived;
  currency: string;
}

export function SummaryCards({ totals, derived, currency }: SummaryCardsProps) {
  const netIsPositive = derived.net_profit >= 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <MetricCard
        label="Выручка (без НДС)"
        value={`${formatAmount(totals.revenue_no_vat)} ${currency}`}
      />
      <MetricCard
        label="Выручка (с НДС)"
        value={`${formatAmount(totals.revenue_with_vat)} ${currency}`}
      />
      <MetricCard
        label="Чистая прибыль"
        value={`${formatAmount(derived.net_profit)} ${currency}`}
        valueClassName={netIsPositive ? "text-green-600" : "text-red-600"}
      />
      <MetricCard
        label="Наценка (выр. ÷ закуп − 1)"
        value={formatPercent(derived.markup_pct)}
      />
    </div>
  );
}

interface MetricCardProps {
  label: string;
  value: string;
  valueClassName?: string;
}

function MetricCard({ label, value, valueClassName }: MetricCardProps) {
  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-1 text-center">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className={cn("text-xl font-bold", valueClassName)}>{value}</span>
      </CardContent>
    </Card>
  );
}
