"use client";

import { useState, useEffect, useCallback } from "react";
import { Plus, Loader2, Trash2, CreditCard, FileText } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  fetchPlanFactItems,
  deletePlanFactItem,
} from "@/features/plan-fact/api";
import { PlanFactSheet } from "./plan-fact-sheet";
import { PlanFactCreateDialog } from "./plan-fact-create-dialog";
import { PlanFactTotals } from "./plan-fact-totals";
import type { PlanFactItem } from "@/entities/finance";

interface PlanFactStepProps {
  quoteId: string;
  dealId: string | null;
  userRoles: string[];
}

const WRITE_ROLES = ["finance", "admin"];

function canWrite(roles: string[]): boolean {
  return roles.some((r) => WRITE_ROLES.includes(r));
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "---";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatAmount(amount: number | null, currency: string | null): string {
  if (amount === null || currency === null) return "---";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

function formatVariance(item: PlanFactItem): string {
  if (item.variance_amount === null) return "---";
  const prefix = item.variance_amount > 0 ? "+" : "";
  return `${prefix}${new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(item.variance_amount)}`;
}

function getStatusLabel(item: PlanFactItem): { label: string; style: string } {
  if (item.actual_amount !== null) {
    return { label: "Оплачено", style: "bg-green-100 text-green-700" };
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const planned = new Date(item.planned_date);
  planned.setHours(0, 0, 0, 0);
  if (planned < today) {
    return { label: "Просрочено", style: "bg-red-100 text-red-700" };
  }
  return { label: "Запланировано", style: "bg-blue-100 text-blue-700" };
}

export function PlanFactStep({
  quoteId,
  dealId,
  userRoles,
}: PlanFactStepProps) {
  const [items, setItems] = useState<PlanFactItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [sheetItem, setSheetItem] = useState<PlanFactItem | null>(null);
  const [deleteItem, setDeleteItem] = useState<PlanFactItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const hasWriteAccess = canWrite(userRoles);

  const loadItems = useCallback(async () => {
    if (!dealId) return;
    setLoading(true);
    try {
      const data = await fetchPlanFactItems(dealId);
      setItems(data);
    } catch {
      toast.error("Не удалось загрузить план-факт данные");
    } finally {
      setLoading(false);
    }
  }, [dealId]);

  useEffect(() => {
    if (dealId) {
      loadItems();
    } else {
      setLoading(false);
    }
  }, [dealId, loadItems]);

  async function handleDelete() {
    if (!deleteItem || !dealId) return;
    setDeleting(true);
    try {
      await deletePlanFactItem(dealId, deleteItem.id);
      setDeleteItem(null);
      loadItems();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Не удалось удалить платёж";
      toast.error(message);
    } finally {
      setDeleting(false);
    }
  }

  // No deal state
  if (!dealId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <FileText size={40} strokeWidth={1} className="text-muted-foreground" />
        <p className="text-sm text-muted-foreground mt-3 max-w-sm">
          Сделка ещё не создана. План-факт станет доступен после подписания
          спецификации.
        </p>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center p-6">
        <Loader2 className="animate-spin text-muted-foreground" size={24} />
      </div>
    );
  }

  // Empty state
  if (items.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <CreditCard
          size={40}
          strokeWidth={1}
          className="text-muted-foreground"
        />
        <p className="text-sm text-muted-foreground mt-3">
          Плановые платежи ещё не созданы
        </p>
        {hasWriteAccess && (
          <>
            <Button
              variant="outline"
              size="sm"
              className="mt-4"
              onClick={() => setCreateOpen(true)}
            >
              <Plus size={14} />
              Добавить платёж
            </Button>
            <PlanFactCreateDialog
              dealId={dealId}
              open={createOpen}
              onOpenChange={setCreateOpen}
              onSuccess={loadItems}
            />
          </>
        )}
      </div>
    );
  }

  return (
    <div className="flex-1 min-w-0 flex flex-col">
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {/* Header with create button */}
        {hasWriteAccess && (
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
              План-факт платежей
            </h3>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCreateOpen(true)}
            >
              <Plus size={14} />
              Добавить платёж
            </Button>
          </div>
        )}

        {/* Table */}
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Категория</TableHead>
                <TableHead>Описание</TableHead>
                <TableHead className="text-right">План. дата</TableHead>
                <TableHead className="text-right">План. сумма</TableHead>
                <TableHead className="text-right">Факт. дата</TableHead>
                <TableHead className="text-right">Факт. сумма</TableHead>
                <TableHead className="text-right">Отклонение</TableHead>
                <TableHead>Статус</TableHead>
                {hasWriteAccess && <TableHead className="w-[100px]">Действия</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => {
                const status = getStatusLabel(item);
                const isUnpaid = item.actual_amount === null;

                return (
                  <TableRow key={item.id}>
                    <TableCell>
                      <Badge
                        className={
                          item.category.is_income
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }
                      >
                        {item.category.name}
                      </Badge>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate text-sm">
                      {item.description || "---"}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums">
                      {formatDate(item.planned_date)}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums font-medium">
                      {formatAmount(item.planned_amount, item.planned_currency)}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums">
                      {formatDate(item.actual_date)}
                    </TableCell>
                    <TableCell className="text-right text-sm tabular-nums font-medium">
                      {formatAmount(item.actual_amount, item.actual_currency)}
                    </TableCell>
                    <TableCell
                      className={`text-right text-sm tabular-nums ${
                        item.variance_amount !== null && item.variance_amount > 0
                          ? "text-red-600"
                          : item.variance_amount !== null &&
                              item.variance_amount < 0
                            ? "text-green-600"
                            : ""
                      }`}
                    >
                      {formatVariance(item)}
                    </TableCell>
                    <TableCell>
                      <Badge className={`border-0 ${status.style}`}>
                        {status.label}
                      </Badge>
                    </TableCell>
                    {hasWriteAccess && (
                      <TableCell>
                        {isUnpaid && (
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 px-2 text-xs"
                              onClick={() => setSheetItem(item)}
                            >
                              Оплатить
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                              onClick={() => setDeleteItem(item)}
                            >
                              <Trash2 size={14} />
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>

        {/* Totals */}
        <PlanFactTotals items={items} />
      </div>

      {/* PlanFactSheet for recording actual payment */}
      {sheetItem && (
        <PlanFactSheet
          item={sheetItem}
          open={!!sheetItem}
          onOpenChange={(open) => {
            if (!open) setSheetItem(null);
          }}
          onSuccess={() => {
            setSheetItem(null);
            loadItems();
          }}
        />
      )}

      {/* PlanFactCreateDialog */}
      <PlanFactCreateDialog
        dealId={dealId}
        open={createOpen}
        onOpenChange={setCreateOpen}
        onSuccess={loadItems}
      />

      {/* Delete confirmation dialog */}
      <Dialog
        open={!!deleteItem}
        onOpenChange={(open) => {
          if (!open) setDeleteItem(null);
        }}
      >
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Удалить платёж?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Платёж &laquo;{deleteItem?.description || deleteItem?.category.name}
            &raquo; будет удалён. Это действие нельзя отменить.
          </p>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteItem(null)}
              disabled={deleting}
            >
              Отмена
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting && <Loader2 size={14} className="animate-spin" />}
              Удалить
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
