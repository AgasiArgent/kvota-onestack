"use client";

import type { PlanFactItem } from "@/entities/finance";

interface PlanFactTotalsProps {
  items: PlanFactItem[];
}

interface CurrencyTotals {
  currency: string;
  plannedIncome: number;
  plannedExpense: number;
  actualIncome: number;
  actualExpense: number;
}

function calculateTotals(items: PlanFactItem[]): CurrencyTotals[] {
  const byCurrency = new Map<string, CurrencyTotals>();

  for (const item of items) {
    const currency = item.planned_currency;
    const existing = byCurrency.get(currency) ?? {
      currency,
      plannedIncome: 0,
      plannedExpense: 0,
      actualIncome: 0,
      actualExpense: 0,
    };

    if (item.category.is_income) {
      existing.plannedIncome += item.planned_amount;
      if (item.actual_amount !== null) {
        existing.actualIncome += item.actual_amount;
      }
    } else {
      existing.plannedExpense += item.planned_amount;
      if (item.actual_amount !== null) {
        existing.actualExpense += item.actual_amount;
      }
    }

    byCurrency.set(currency, existing);
  }

  return Array.from(byCurrency.values());
}

function formatAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function PlanFactTotals({ items }: PlanFactTotalsProps) {
  if (items.length === 0) {
    return null;
  }

  const totals = calculateTotals(items);

  return (
    <div className="rounded-lg border bg-muted/30 p-4">
      {totals.map((t) => {
        const plannedBalance = t.plannedIncome - t.plannedExpense;
        const actualBalance = t.actualIncome - t.actualExpense;

        return (
          <div
            key={t.currency}
            className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm"
          >
            <div>
              <span className="text-muted-foreground">Поступления план:</span>
              <div className="font-medium tabular-nums">
                {formatAmount(t.plannedIncome, t.currency)}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Поступления факт:</span>
              <div className="font-medium text-green-600 tabular-nums">
                {formatAmount(t.actualIncome, t.currency)}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Выплаты план:</span>
              <div className="font-medium tabular-nums">
                {formatAmount(t.plannedExpense, t.currency)}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Выплаты факт:</span>
              <div className="font-medium text-red-600 tabular-nums">
                {formatAmount(t.actualExpense, t.currency)}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Баланс:</span>
              <div className="space-y-0.5">
                <div
                  className={`font-bold tabular-nums ${
                    plannedBalance >= 0 ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {formatAmount(plannedBalance, t.currency)}{" "}
                  <span className="font-normal text-muted-foreground text-xs">
                    план
                  </span>
                </div>
                <div
                  className={`font-bold tabular-nums ${
                    actualBalance >= 0 ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {formatAmount(actualBalance, t.currency)}{" "}
                  <span className="font-normal text-muted-foreground text-xs">
                    факт
                  </span>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
