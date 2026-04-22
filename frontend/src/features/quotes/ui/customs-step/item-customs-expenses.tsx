"use client";

import { useEffect, useState, useTransition } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  createItemExpense,
  deleteItemExpense,
  fetchItemExpenses,
  type CustomsItemExpense,
} from "@/entities/customs-expense";

interface ItemCustomsExpensesProps {
  quoteId: string;
  quoteItemId: string;
  itemLabel: string;
  userRoles: string[];
}

const CAN_WRITE_ROLES = new Set(["customs", "head_of_customs", "admin"]);

const RUB_FORMATTER = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 0,
});

/**
 * Per-item customs costs (testing, translations, stickers) — visible only
 * when a row is selected in the handsontable above. RUB only.
 */
export function ItemCustomsExpenses({
  quoteId,
  quoteItemId,
  itemLabel,
  userRoles,
}: ItemCustomsExpensesProps) {
  const [expenses, setExpenses] = useState<CustomsItemExpense[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newAmount, setNewAmount] = useState<string>("");
  const [pending, startTransition] = useTransition();

  const canWrite = userRoles.some((r) => CAN_WRITE_ROLES.has(r));
  const revalidatePath = `/quotes/${quoteId}`;

  useEffect(() => {
    let cancelled = false;
    setLoaded(false);
    fetchItemExpenses(quoteItemId).then((rows) => {
      if (!cancelled) {
        setExpenses(rows);
        setLoaded(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [quoteItemId]);

  async function handleAdd() {
    const label = newLabel.trim();
    const amount = Number.parseFloat(newAmount);
    if (!label) {
      toast.error("Укажите наименование расхода");
      return;
    }
    if (!Number.isFinite(amount) || amount < 0) {
      toast.error("Сумма должна быть неотрицательным числом");
      return;
    }
    startTransition(async () => {
      try {
        const { expense_id } = await createItemExpense({
          quote_item_id: quoteItemId,
          label,
          amount_rub: amount,
          revalidate_path: revalidatePath,
        });
        setExpenses((prev) => [
          ...prev,
          {
            id: expense_id,
            quote_item_id: quoteItemId,
            label,
            amount_rub: amount,
            notes: null,
            created_at: new Date().toISOString(),
            created_by: null,
          },
        ]);
        setNewLabel("");
        setNewAmount("");
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Не удалось добавить");
      }
    });
  }

  async function handleDelete(expenseId: string) {
    startTransition(async () => {
      try {
        await deleteItemExpense({
          expense_id: expenseId,
          revalidate_path: revalidatePath,
        });
        setExpenses((prev) => prev.filter((e) => e.id !== expenseId));
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Не удалось удалить");
      }
    });
  }

  const total = expenses.reduce((sum, e) => sum + Number(e.amount_rub || 0), 0);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0 pb-3">
        <CardTitle className="text-sm">
          Расходы по позиции{" "}
          <span className="text-muted-foreground font-normal">{itemLabel}</span>
        </CardTitle>
        <div className="text-sm font-semibold tabular-nums text-foreground">
          Σ {RUB_FORMATTER.format(total)}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {!loaded && (
          <div className="py-2 text-xs text-muted-foreground">Загрузка…</div>
        )}

        {loaded && expenses.length === 0 && (
          <div className="py-1 text-xs text-muted-foreground">
            Нет персональных расходов. Добавьте испытания, перевод, стикеры и т.п.
          </div>
        )}

        {expenses.map((exp) => (
          <div
            key={exp.id}
            className="flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1.5"
          >
            <span className="flex-1 text-sm text-foreground">{exp.label}</span>
            <span className="w-28 text-right text-sm font-semibold tabular-nums text-foreground">
              {RUB_FORMATTER.format(Number(exp.amount_rub || 0))}
            </span>
            {canWrite && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                onClick={() => handleDelete(exp.id)}
                disabled={pending}
                aria-label="Удалить расход"
              >
                <Trash2 size={13} />
              </Button>
            )}
          </div>
        ))}

        {canWrite && (
          <div className="mt-1 flex flex-wrap items-center gap-2 border-t border-border pt-3">
            <Input
              placeholder="Наименование (испытания, перевод, …)"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              className="flex-1 min-w-[160px]"
              disabled={pending}
            />
            <Input
              type="number"
              min="0"
              step="0.01"
              placeholder="0"
              value={newAmount}
              onChange={(e) => setNewAmount(e.target.value)}
              className="w-32 text-right tabular-nums"
              disabled={pending}
            />
            <span className="text-xs text-muted-foreground">₽</span>
            <Button size="sm" onClick={handleAdd} disabled={pending}>
              <Plus size={13} />
              Добавить
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
