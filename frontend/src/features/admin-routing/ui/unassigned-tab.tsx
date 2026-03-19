"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Inbox } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { assignUnassignedItem } from "../api/routing-api";
import { UserSelect } from "./user-select";
import type { UnassignedItem } from "../model/types";

interface Props {
  items: UnassignedItem[];
  orgId: string;
}

interface RowState {
  userId: string;
  createBrandRule: boolean;
}

export function UnassignedTab({ items, orgId }: Props) {
  const router = useRouter();
  const [rowStates, setRowStates] = useState<Record<string, RowState>>({});
  const [assigningId, setAssigningId] = useState<string | null>(null);

  function getRowState(itemId: string): RowState {
    return rowStates[itemId] ?? { userId: "", createBrandRule: false };
  }

  function updateRowState(itemId: string, partial: Partial<RowState>) {
    setRowStates((prev) => ({
      ...prev,
      [itemId]: { ...getRowState(itemId), ...partial },
    }));
  }

  async function handleAssign(item: UnassignedItem) {
    const state = getRowState(item.id);
    if (!state.userId) return;

    setAssigningId(item.id);
    try {
      await assignUnassignedItem(
        item.id,
        state.userId,
        state.createBrandRule,
        orgId,
        item.brand
      );
      toast.success("Позиция назначена");
      router.refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ошибка назначения";
      toast.error(msg);
    } finally {
      setAssigningId(null);
    }
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "—";
    return new Date(dateStr).toLocaleDateString("ru-RU");
  }

  if (items.length === 0) {
    return (
      <div className="space-y-8">
        <div>
          <h2 className="text-lg font-semibold text-text">Нераспределённые позиции</h2>
          <p className="text-sm text-text-muted mt-1">
            Позиции, не попавшие ни под одно правило маршрутизации
          </p>
        </div>
        <div className="py-12 text-center">
          <CheckCircle2 size={40} className="mx-auto text-success mb-3" />
          <p className="text-text-muted mb-1">Все заявки распределены</p>
          <p className="text-xs text-text-subtle">
            Новые нераспределённые позиции появятся здесь автоматически
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-text">Нераспределённые позиции</h2>
        <p className="text-sm text-text-muted mt-1">
          {items.length} {items.length === 1 ? "позиция требует" : "позиций требуют"} назначения
        </p>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>КП</TableHead>
            <TableHead>Бренд</TableHead>
            <TableHead>Клиент</TableHead>
            <TableHead>Менеджер продаж</TableHead>
            <TableHead>Дата</TableHead>
            <TableHead>Назначить МОЗ</TableHead>
            <TableHead className="w-[180px]" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const state = getRowState(item.id);
            const isAssigning = assigningId === item.id;

            return (
              <TableRow key={item.id}>
                <TableCell className="font-medium">{item.quote_idn}</TableCell>
                <TableCell className="text-text-muted">
                  {item.brand ?? "—"}
                </TableCell>
                <TableCell className="text-text-muted">
                  {item.customer_name ?? "—"}
                </TableCell>
                <TableCell className="text-text-muted">
                  {item.sales_manager_name ?? "—"}
                </TableCell>
                <TableCell className="text-text-muted">
                  {formatDate(item.created_at)}
                </TableCell>
                <TableCell>
                  <div className="max-w-[200px]">
                    <UserSelect
                      value={state.userId}
                      onValueChange={(val) =>
                        updateRowState(item.id, { userId: val })
                      }
                      orgId={orgId}
                      disabled={isAssigning}
                    />
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-3">
                    {item.brand && (
                      <label className="flex items-center gap-1.5 text-xs cursor-pointer whitespace-nowrap">
                        <input
                          type="checkbox"
                          checked={state.createBrandRule}
                          onChange={(e) =>
                            updateRowState(item.id, {
                              createBrandRule: e.target.checked,
                            })
                          }
                          disabled={isAssigning}
                          className="size-3.5 rounded accent-accent"
                        />
                        <span className="text-text-muted">Закрепить бренд</span>
                      </label>
                    )}
                    <Button
                      size="sm"
                      onClick={() => handleAssign(item)}
                      disabled={!state.userId || isAssigning}
                      className="bg-accent text-white hover:bg-accent-hover"
                    >
                      <Inbox size={12} />
                      Назначить
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
