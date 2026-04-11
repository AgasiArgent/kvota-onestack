"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { createClient } from "@/shared/lib/supabase/client";
import {
  createLogisticsExpense,
  updateLogisticsExpense,
  deleteLogisticsExpense,
} from "@/entities/quote/mutations";
import { SUPPORTED_CURRENCIES } from "@/shared/lib/currencies";

interface ExpenseRow {
  id: string;
  description: string;
  expense_type: string;
  amount: number | null;
  currency: string;
  isNew?: boolean;
}

interface AdditionalExpensesProps {
  invoiceId: string;
}

export function AdditionalExpenses({ invoiceId }: AdditionalExpensesProps) {
  const router = useRouter();
  const [expenses, setExpenses] = useState<ExpenseRow[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [adding, setAdding] = useState(false);

  // Load existing expenses from DB
  useEffect(() => {
    const supabase = createClient();
    supabase
      .from("logistics_additional_expenses")
      .select("id, expense_type, description, amount, currency")
      .eq("invoice_id", invoiceId)
      .order("created_at", { ascending: true })
      .then(({ data }) => {
        setExpenses(
          (data ?? []).map((row) => ({
            id: row.id,
            description: row.description ?? "",
            expense_type: row.expense_type,
            amount: row.amount,
            currency: row.currency,
          }))
        );
        setLoaded(true);
      });
  }, [invoiceId]);

  const saveField = useCallback(
    async (expenseId: string, field: string, rawValue: string) => {
      let value: unknown;
      if (field === "amount") {
        const parsed = parseFloat(rawValue);
        value = isNaN(parsed) ? 0 : parsed;
      } else {
        value = rawValue;
      }

      try {
        await updateLogisticsExpense(expenseId, { [field]: value });
        router.refresh();
      } catch {
        toast.error("Не удалось сохранить расход");
      }
    },
    [router]
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

  function handleBlur(id: string, field: string) {
    const exp = expenses.find((e) => e.id === id);
    if (!exp || exp.isNew) return;

    const rawValue =
      field === "amount" ? String(exp.amount ?? 0) : String(exp[field as keyof ExpenseRow] ?? "");
    saveField(id, field, rawValue);
  }

  async function handleAdd() {
    setAdding(true);
    try {
      const expense = await createLogisticsExpense({
        invoice_id: invoiceId,
        expense_type: "other",
        description: "",
        amount: 0,
        currency: "USD",
      });

      setExpenses((prev) => [
        ...prev,
        {
          id: expense.id,
          description: expense.description ?? "",
          expense_type: expense.expense_type,
          amount: expense.amount,
          currency: expense.currency,
        },
      ]);
      router.refresh();
    } catch {
      toast.error("Не удалось добавить расход");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(id: string) {
    try {
      await deleteLogisticsExpense(id);
      setExpenses((prev) => prev.filter((e) => e.id !== id));
      toast.success("Расход удалён");
      router.refresh();
    } catch {
      toast.error("Не удалось удалить расход");
    }
  }

  if (!loaded) {
    return (
      <div className="px-4 py-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" />
        Загрузка расходов...
      </div>
    );
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
                      saveField(exp.id, "currency", e.target.value);
                    }}
                  >
                    {SUPPORTED_CURRENCIES.map((c) => (
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
          disabled={adding}
        >
          {adding ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Plus size={14} />
          )}
          Добавить расход
        </Button>
      </div>
    </div>
  );
}
