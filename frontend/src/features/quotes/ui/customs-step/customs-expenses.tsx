"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { createClient } from "@/shared/lib/supabase/client";
import type { Json } from "@/shared/types/database.types";

const CURRENCIES = ["RUB", "USD", "EUR", "CNY", "TRY"] as const;

interface ExpenseField {
  key: string;
  currencyKey: string;
  label: string;
}

const EXPENSE_FIELDS: ExpenseField[] = [
  {
    key: "brokerage_hub",
    currencyKey: "brokerage_hub_currency",
    label: "Брокерские (хаб)",
  },
  {
    key: "brokerage_customs",
    currencyKey: "brokerage_customs_currency",
    label: "Брокерские (таможня)",
  },
  {
    key: "warehousing_at_customs",
    currencyKey: "warehousing_at_customs_currency",
    label: "СВХ",
  },
  {
    key: "customs_documentation",
    currencyKey: "customs_documentation_currency",
    label: "Документация",
  },
  {
    key: "brokerage_extra",
    currencyKey: "brokerage_extra_currency",
    label: "Доп. брокерские",
  },
];

interface CalcVarsRecord {
  id: string;
  variables: Record<string, unknown>;
}

interface CustomsExpensesProps {
  quoteId: string;
}

export function CustomsExpenses({ quoteId }: CustomsExpensesProps) {
  const router = useRouter();
  const [calcVars, setCalcVars] = useState<CalcVarsRecord | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [values, setValues] = useState<Record<string, number | string>>({});

  useEffect(() => {
    const supabase = createClient();
    supabase
      .from("quote_calculation_variables")
      .select("id, variables")
      .eq("quote_id", quoteId)
      .limit(1)
      .then(({ data }) => {
        const record = data?.[0] ?? null;
        if (record) {
          setCalcVars({
            id: record.id,
            variables: (record.variables as Record<string, unknown>) ?? {},
          });
          const vars = (record.variables as Record<string, unknown>) ?? {};
          const initial: Record<string, number | string> = {};
          for (const field of EXPENSE_FIELDS) {
            initial[field.key] = Number(vars[field.key] ?? 0);
            initial[field.currencyKey] = String(
              vars[field.currencyKey] ?? "RUB"
            );
          }
          setValues(initial);
        } else {
          const initial: Record<string, number | string> = {};
          for (const field of EXPENSE_FIELDS) {
            initial[field.key] = 0;
            initial[field.currencyKey] = "RUB";
          }
          setValues(initial);
        }
        setLoaded(true);
      });
  }, [quoteId]);

  const saveField = useCallback(
    async (fieldKey: string, fieldValue: number | string) => {
      const supabase = createClient();

      try {
        if (calcVars) {
          const updatedVars = { ...calcVars.variables, [fieldKey]: fieldValue };
          await supabase
            .from("quote_calculation_variables")
            .update({ variables: updatedVars as unknown as Json })
            .eq("id", calcVars.id);
          setCalcVars({ ...calcVars, variables: updatedVars });
        } else {
          const newVars: Record<string, unknown> = { [fieldKey]: fieldValue };
          const { data } = await supabase
            .from("quote_calculation_variables")
            .insert({
              quote_id: quoteId,
              variables: newVars as unknown as Json,
            })
            .select("id, variables")
            .single();
          if (data) {
            setCalcVars({
              id: data.id,
              variables: (data.variables as Record<string, unknown>) ?? {},
            });
          }
        }
        router.refresh();
      } catch {
        toast.error("Не удалось сохранить расход");
      }
    },
    [calcVars, quoteId, router]
  );

  function handleValueChange(key: string, rawValue: string) {
    const parsed = parseFloat(rawValue);
    setValues((prev) => ({
      ...prev,
      [key]: isNaN(parsed) ? 0 : parsed,
    }));
  }

  function handleCurrencyChange(currencyKey: string, currency: string) {
    setValues((prev) => ({ ...prev, [currencyKey]: currency }));
    saveField(currencyKey, currency);
  }

  function handleBlur(key: string) {
    const val = values[key];
    const numVal = typeof val === "number" ? val : parseFloat(String(val)) || 0;
    saveField(key, numVal);
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
    <div className="rounded-lg border border-amber-300 bg-gradient-to-br from-amber-50 to-amber-100 p-4">
      <h4 className="text-xs font-semibold text-amber-700 uppercase tracking-wide mb-1">
        Общие расходы на КП
      </h4>
      <p className="text-xs text-amber-800 mb-4">
        Укажите общие расходы на всю квоту. Выберите валюту для каждого поля.
      </p>

      <div className="grid grid-cols-2 gap-3">
        {EXPENSE_FIELDS.map((field) => (
          <div key={field.key} className="flex items-center gap-2">
            <span className="text-sm text-amber-900 min-w-[140px] shrink-0">
              {field.label}
            </span>
            <input
              type="number"
              step="0.01"
              min="0"
              className="w-24 h-7 px-1.5 text-right font-mono text-sm border border-border rounded bg-white focus:outline-none focus:border-ring focus:ring-1 focus:ring-ring/50 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              value={values[field.key] ?? 0}
              onChange={(e) => handleValueChange(field.key, e.target.value)}
              onBlur={() => handleBlur(field.key)}
            />
            <select
              className="h-7 px-1 text-xs border border-border rounded bg-white focus:outline-none focus:border-ring focus:ring-1 focus:ring-ring/50 cursor-pointer"
              value={String(values[field.currencyKey] ?? "RUB")}
              onChange={(e) =>
                handleCurrencyChange(field.currencyKey, e.target.value)
              }
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
    </div>
  );
}
