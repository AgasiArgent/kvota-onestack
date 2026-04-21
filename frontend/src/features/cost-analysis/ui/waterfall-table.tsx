import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { formatAmount, formatPercent, pctOfRevenue } from "./format";
import type {
  CostAnalysisDerived,
  CostAnalysisLogisticsBreakdown,
  CostAnalysisTotals,
} from "../types";

interface WaterfallTableProps {
  totals: CostAnalysisTotals;
  logistics: CostAnalysisLogisticsBreakdown;
  derived: CostAnalysisDerived;
  currency: string;
}

export function WaterfallTable({
  totals,
  logistics,
  derived,
  currency,
}: WaterfallTableProps) {
  const revenue = totals.revenue_no_vat;

  const grossProfitClass =
    derived.gross_profit >= 0 ? "text-green-600" : "text-red-600";
  const netProfitClass =
    derived.net_profit >= 0 ? "text-green-600" : "text-red-600";

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="text-left">Статья</TableHead>
          <TableHead className="text-right">{`Сумма (${currency})`}</TableHead>
          <TableHead className="text-right">% от выручки</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {/* Revenue subtotal */}
        <SubtotalRow
          label="Выручка (без НДС)"
          amount={revenue}
          percent={revenue > 0 ? 100 : 0}
        />
        {/* Purchase */}
        <LineRow
          label="Сумма закупки"
          amount={totals.purchase}
          revenue={revenue}
        />
        {/* Logistics total */}
        <LineRow
          label="Логистика (итого)"
          amount={totals.logistics}
          revenue={revenue}
        />
        {/* W2-W10 breakdown */}
        <IndentRow label="Логистика до СВХ (W2)" amount={logistics.W2_supplier_hub} />
        <IndentRow label="ТР — РФ (W3)" amount={logistics.W3_hub_customs} />
        <IndentRow label="РФ — КУДА (W4)" amount={logistics.W4_customs_client} />
        <IndentRow label="Брокерские до РФ (W5)" amount={logistics.W5_brokerage_hub} />
        <IndentRow label="Брокерские в РФ (W6)" amount={logistics.W6_brokerage_customs} />
        <IndentRow label="Порт и СВХ в РФ (W7)" amount={logistics.W7_warehousing} />
        <IndentRow label="Сертификация (W8)" amount={logistics.W8_documentation} />
        <IndentRow label="Доп. расход (W9)" amount={logistics.W9_extra} />
        <IndentRow label="Страховка (W10)" amount={logistics.W10_insurance} />
        {/* Customs + excise */}
        <LineRow
          label="Пошлина"
          amount={totals.customs}
          revenue={revenue}
        />
        <LineRow
          label="Акциз"
          amount={totals.excise}
          revenue={revenue}
        />
        {/* Gross Profit subtotal */}
        <SubtotalRow
          label="= Валовая прибыль (Gross Profit)"
          amount={derived.gross_profit}
          percent={pctOfRevenue(derived.gross_profit, revenue)}
          amountClassName={grossProfitClass}
        />
        {/* Financial expenses */}
        <LineRow
          label="Вознаграждение ЛПР (DM fee)"
          amount={totals.dm_fee}
          revenue={revenue}
        />
        <LineRow
          label="Резерв курсовой разницы (Forex)"
          amount={totals.forex}
          revenue={revenue}
        />
        <LineRow
          label="Комиссия фин. агента (Financial agent fee)"
          amount={totals.financial_agent_fee}
          revenue={revenue}
        />
        <LineRow
          label="Стоимость финансирования (Financing)"
          amount={totals.financing}
          revenue={revenue}
        />
        {/* Net Profit subtotal */}
        <SubtotalRow
          label="= Чистая прибыль (Net Profit)"
          amount={derived.net_profit}
          percent={pctOfRevenue(derived.net_profit, revenue)}
          amountClassName={netProfitClass}
        />
        {/* Markup */}
        <TableRow>
          <TableCell>Наценка (Markup %)</TableCell>
          <TableCell className="text-right font-semibold">
            {formatPercent(derived.markup_pct)}
          </TableCell>
          <TableCell />
        </TableRow>
      </TableBody>
    </Table>
  );
}

interface LineRowProps {
  label: string;
  amount: number;
  revenue: number;
}

function LineRow({ label, amount, revenue }: LineRowProps) {
  return (
    <TableRow>
      <TableCell>{label}</TableCell>
      <TableCell className="text-right">{formatAmount(amount)}</TableCell>
      <TableCell className="text-right text-muted-foreground">
        {formatPercent(pctOfRevenue(amount, revenue))}
      </TableCell>
    </TableRow>
  );
}

interface IndentRowProps {
  label: string;
  amount: number;
}

function IndentRow({ label, amount }: IndentRowProps) {
  return (
    <TableRow>
      <TableCell className="pl-8 text-xs text-muted-foreground">
        {label}
      </TableCell>
      <TableCell className="text-right text-xs text-muted-foreground">
        {formatAmount(amount)}
      </TableCell>
      <TableCell />
    </TableRow>
  );
}

interface SubtotalRowProps {
  label: string;
  amount: number;
  percent: number;
  amountClassName?: string;
}

function SubtotalRow({
  label,
  amount,
  percent,
  amountClassName,
}: SubtotalRowProps) {
  return (
    <TableRow className="bg-muted/50 font-semibold">
      <TableCell>{label}</TableCell>
      <TableCell className={cn("text-right", amountClassName)}>
        {formatAmount(amount)}
      </TableCell>
      <TableCell className="text-right">{formatPercent(percent)}</TableCell>
    </TableRow>
  );
}
