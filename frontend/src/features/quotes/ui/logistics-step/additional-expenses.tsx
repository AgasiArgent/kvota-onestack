"use client";

import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";

const CURRENCIES = ["USD", "EUR", "CNY", "RUB"] as const;

interface ExpenseRow {
  id: string;
  description: string;
  amount: number | null;
  currency: string;
}

function createId(): string {
  return crypto.randomUUID();
}

const DEFAULT_EXPENSES: ExpenseRow[] = [
  { id: createId(), description: "\u0421\u0412\u0425", amount: null, currency: "USD" },
  { id: createId(), description: "\u0421\u0442\u0440\u0430\u0445\u043E\u0432\u043A\u0430", amount: null, currency: "USD" },
];

interface AdditionalExpensesProps {
  invoiceId: string;
}

export function AdditionalExpenses({ invoiceId }: AdditionalExpensesProps) {
  const [expenses, setExpenses] = useState<ExpenseRow[]>(() =>
    DEFAULT_EXPENSES.map((e) => ({ ...e, id: createId() }))
  );

  function handleChange(id: string, field: keyof ExpenseRow, value: string) {
    setExpenses((prev) =>
      prev.map((exp) => {
        if (exp.id !== id) return exp;
        if (field === "amount") {
          const parsed = parseFloat(value);
          return { ...exp, amount: isNaN(parsed) ? null : parsed };
        }
        return { ...exp, [field]: value };
      })
    );
  }

  function handleBlur(id: string, field: keyof ExpenseRow) {
    const exp = expenses.find((e) => e.id === id);
    if (exp) {
      console.log(`[logistics] expense ${field} =`, exp[field], "invoice:", invoiceId);
    }
  }

  function handleAdd() {
    setExpenses((prev) => [
      ...prev,
      { id: createId(), description: "", amount: null, currency: "USD" },
    ]);
  }

  function handleRemove(id: string) {
    setExpenses((prev) => prev.filter((e) => e.id !== id));
  }

  return (
    <div>
      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-2 border-b border-border bg-muted/30">
        Доп. расходы
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="text-left font-medium px-4 py-1.5">Описание</th>
              <th className="text-right font-medium px-2 py-1.5 w-28">Сумма</th>
              <th className="text-left font-medium px-2 py-1.5 w-20">Валюта</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {expenses.map((exp) => (
              <tr key={exp.id} className="border-b border-border/50">
                <td className="px-4 py-1">
                  <input
                    type="text"
                    className="w-full h-7 px-1.5 text-sm border border-border rounded bg-transparent focus:outline-none focus:border-ring focus:ring-1 focus:ring-ring/50"
                    value={exp.description}
                    onChange={(e) =>
                      handleChange(exp.id, "description", e.target.value)
                    }
                    onBlur={() => handleBlur(exp.id, "description")}
                    placeholder="Название расхода"
                  />
                </td>
                <td className="px-2 py-1">
                  <input
                    type="number"
                    step="0.01"
                    className="w-full h-7 px-1.5 text-right font-mono text-sm border border-border rounded bg-transparent focus:outline-none focus:border-ring focus:ring-1 focus:ring-ring/50 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    value={exp.amount ?? ""}
                    onChange={(e) =>
                      handleChange(exp.id, "amount", e.target.value)
                    }
                    onBlur={() => handleBlur(exp.id, "amount")}
                    placeholder="0.00"
                  />
                </td>
                <td className="px-2 py-1">
                  <select
                    className="w-full h-7 px-1 text-xs border border-border rounded bg-transparent focus:outline-none focus:border-ring focus:ring-1 focus:ring-ring/50 cursor-pointer"
                    value={exp.currency}
                    onChange={(e) => {
                      handleChange(exp.id, "currency", e.target.value);
                      handleBlur(exp.id, "currency");
                    }}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-1 py-1">
                  <button
                    type="button"
                    className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                    onClick={() => handleRemove(exp.id)}
                    aria-label="Удалить расход"
                  >
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-2">
        <Button
          variant="ghost"
          size="sm"
          className="text-xs text-muted-foreground"
          onClick={handleAdd}
        >
          <Plus size={14} />
          Добавить расход
        </Button>
      </div>
    </div>
  );
}
