"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ClipboardList, Check, Loader2 } from "lucide-react";
import { toast, Toaster } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  ProcurementQueueItem,
  ProcurementQueueStatus,
  BrandGroup,
} from "@/entities/phmb-quote/types";
import {
  setProcurementPrice,
  updateQueueItemStatus,
} from "@/entities/phmb-quote/mutations";

interface ProcurementQueueProps {
  items: ProcurementQueueItem[];
  brandGroups: BrandGroup[];
  initialStatus?: ProcurementQueueStatus;
  initialBrandGroupId?: string;
}

const STATUS_FILTERS: Array<{
  value: string;
  label: string;
}> = [
  { value: "", label: "Все" },
  { value: "new", label: "Новые" },
  { value: "requested", label: "Запрошено" },
  { value: "priced", label: "С ценой" },
];

const STATUS_BADGE: Record<
  ProcurementQueueStatus,
  { label: string; className: string }
> = {
  new: {
    label: "Новый",
    className: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  },
  requested: {
    label: "Запрошено",
    className: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  },
  priced: {
    label: "С ценой",
    className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  },
};

function formatPrice(value: number | null): string {
  if (value === null || value === 0) return "\u2014";
  return new Intl.NumberFormat("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function ProcurementQueue({
  items,
  brandGroups,
  initialStatus,
  initialBrandGroupId = "",
}: ProcurementQueueProps) {
  const router = useRouter();
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());
  const [priceInputs, setPriceInputs] = useState<Record<string, string>>({});
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());

  const buildUrl = useCallback(
    (overrides: { status?: string; brand_group_id?: string }) => {
      const params = new URLSearchParams();
      const status =
        overrides.status !== undefined
          ? overrides.status
          : initialStatus ?? "";
      const bgId =
        overrides.brand_group_id !== undefined
          ? overrides.brand_group_id
          : initialBrandGroupId;

      if (status) params.set("status", status);
      if (bgId) params.set("brand_group_id", bgId);

      const qs = params.toString();
      return qs ? `/phmb/procurement?${qs}` : "/phmb/procurement";
    },
    [initialStatus, initialBrandGroupId]
  );

  function handleStatusFilter(value: string) {
    router.push(buildUrl({ status: value }));
  }

  function handleBrandGroupFilter(value: string) {
    router.push(buildUrl({ brand_group_id: value }));
  }

  function handlePriceChange(itemId: string, value: string) {
    setPriceInputs((prev) => ({ ...prev, [itemId]: value }));
  }

  async function handleRequestPrice(item: ProcurementQueueItem) {
    setSavingIds((prev) => new Set(prev).add(item.id));
    try {
      await updateQueueItemStatus(item.id, "requested");
      toast.success(`Запрос цены отправлен: ${item.cat_number}`);
      router.refresh();
    } catch {
      toast.error("Не удалось отправить запрос");
    } finally {
      setSavingIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    }
  }

  async function handleSavePrice(item: ProcurementQueueItem) {
    const priceStr = priceInputs[item.id];
    const price = parseFloat(priceStr);

    if (!priceStr || isNaN(price) || price <= 0) {
      toast.error("Введите корректную цену");
      return;
    }

    setSavingIds((prev) => new Set(prev).add(item.id));
    try {
      await setProcurementPrice(item.id, price);
      setSavedIds((prev) => new Set(prev).add(item.id));
      toast.success(`Цена установлена: ${item.cat_number} — ${formatPrice(price)} CNY`);
      router.refresh();
    } catch {
      toast.error("Не удалось сохранить цену");
    } finally {
      setSavingIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    }
  }

  const pendingCount = items.filter((i) => i.status !== "priced").length;

  return (
    <div className="space-y-4">
      <Toaster position="top-right" richColors />

      {/* Header */}
      <div className="flex items-center gap-3">
        <ClipboardList size={24} className="text-accent" />
        <h1 className="text-2xl font-bold">Очередь закупок PHMB</h1>
        <Badge
          variant="outline"
          className="bg-accent-subtle text-accent text-xs font-semibold"
        >
          {items.length}
        </Badge>
        {pendingCount > 0 && (
          <span className="text-sm text-text-muted">
            ({pendingCount} без цены)
          </span>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Brand group filter */}
        {brandGroups.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Группа:
            </span>
            <div className="flex gap-1.5">
              <Button
                variant={!initialBrandGroupId ? "default" : "outline"}
                size="sm"
                className={
                  !initialBrandGroupId
                    ? "bg-accent text-white hover:bg-accent-hover"
                    : ""
                }
                onClick={() => handleBrandGroupFilter("")}
              >
                Все
              </Button>
              {brandGroups.map((bg) => (
                <Button
                  key={bg.id}
                  variant={initialBrandGroupId === bg.id ? "default" : "outline"}
                  size="sm"
                  className={
                    initialBrandGroupId === bg.id
                      ? "bg-accent text-white hover:bg-accent-hover"
                      : ""
                  }
                  onClick={() => handleBrandGroupFilter(bg.id)}
                >
                  {bg.name}
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* Status filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            Статус:
          </span>
          <div className="flex gap-1.5">
            {STATUS_FILTERS.map((sf) => {
              const isActive =
                sf.value === "" ? !initialStatus : initialStatus === sf.value;
              return (
                <Button
                  key={sf.value}
                  variant={isActive ? "default" : "outline"}
                  size="sm"
                  className={
                    isActive
                      ? "bg-accent text-white hover:bg-accent-hover"
                      : ""
                  }
                  onClick={() => handleStatusFilter(sf.value)}
                >
                  {sf.label}
                </Button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-card border border-border-light rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[140px]">КП</TableHead>
              <TableHead>Клиент</TableHead>
              <TableHead>Бренд</TableHead>
              <TableHead>Артикул</TableHead>
              <TableHead>Наименование</TableHead>
              <TableHead className="text-center w-[80px]">Кол-во</TableHead>
              <TableHead className="w-[120px]">Статус</TableHead>
              <TableHead className="w-[240px]">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => {
              const badge = STATUS_BADGE[item.status];
              const isSaving = savingIds.has(item.id);
              const isSaved = savedIds.has(item.id);

              return (
                <TableRow key={item.id}>
                  <TableCell>
                    <Link
                      href={`/phmb/${item.quote_id}`}
                      className="text-accent font-medium hover:underline"
                    >
                      {item.quote_idn}
                    </Link>
                  </TableCell>
                  <TableCell className="text-text-muted">
                    {item.customer_name}
                  </TableCell>
                  <TableCell className="text-text-muted">
                    {item.brand}
                  </TableCell>
                  <TableCell className="font-medium">
                    {item.cat_number}
                  </TableCell>
                  <TableCell className="max-w-[200px] truncate">
                    {item.product_name}
                  </TableCell>
                  <TableCell className="text-center tabular-nums">
                    {item.quantity}
                  </TableCell>
                  <TableCell>
                    {item.status === "priced" && item.priced_rmb ? (
                      <Badge
                        variant="outline"
                        className={badge.className}
                      >
                        {"\u00A5"}{formatPrice(item.priced_rmb)}
                      </Badge>
                    ) : (
                      <Badge variant="outline" className={badge.className}>
                        {badge.label}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <QueueItemActions
                      item={item}
                      isSaving={isSaving}
                      isSaved={isSaved}
                      priceValue={priceInputs[item.id] ?? ""}
                      onPriceChange={(val) => handlePriceChange(item.id, val)}
                      onRequestPrice={() => handleRequestPrice(item)}
                      onSavePrice={() => handleSavePrice(item)}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
            {items.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={8}
                  className="text-center py-12 text-text-subtle"
                >
                  <ClipboardList
                    size={32}
                    className="mx-auto mb-3 text-text-subtle"
                    strokeWidth={1.5}
                  />
                  <p className="text-sm">
                    Очередь пуста — все позиции имеют цены
                  </p>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

// --- Actions sub-component ---

interface QueueItemActionsProps {
  item: ProcurementQueueItem;
  isSaving: boolean;
  isSaved: boolean;
  priceValue: string;
  onPriceChange: (value: string) => void;
  onRequestPrice: () => void;
  onSavePrice: () => void;
}

function QueueItemActions({
  item,
  isSaving,
  isSaved,
  priceValue,
  onPriceChange,
  onRequestPrice,
  onSavePrice,
}: QueueItemActionsProps) {
  if (item.status === "priced") {
    return (
      <span className="flex items-center gap-1.5 text-xs text-text-subtle">
        <Check size={14} />
        Обработано
      </span>
    );
  }

  if (item.status === "new") {
    return (
      <Button
        variant="outline"
        size="sm"
        disabled={isSaving}
        onClick={onRequestPrice}
        className="text-amber-700 border-amber-300 hover:bg-amber-50"
      >
        {isSaving ? (
          <Loader2 size={14} className="animate-spin" />
        ) : null}
        Запросить
      </Button>
    );
  }

  // status === "requested" — show price input + save button
  return (
    <div className="flex items-center gap-2">
      <Input
        type="number"
        step="0.01"
        min="0.01"
        placeholder="Цена CNY"
        value={priceValue}
        onChange={(e) => onPriceChange(e.target.value)}
        className="w-[100px] h-8 text-sm"
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onSavePrice();
          }
        }}
      />
      <Button
        size="sm"
        disabled={isSaving || isSaved}
        onClick={onSavePrice}
        className="bg-accent text-white hover:bg-accent-hover h-8"
      >
        {isSaving ? (
          <Loader2 size={14} className="animate-spin" />
        ) : isSaved ? (
          <Check size={14} />
        ) : null}
        Сохранить
      </Button>
    </div>
  );
}
