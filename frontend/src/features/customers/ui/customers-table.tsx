"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Search, Plus, List, LayoutGrid } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Toggle } from "@/components/ui/toggle";
import { CreateCustomerDialog } from "./create-customer-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { CustomerListItem, CustomerFinancials } from "@/entities/customer";

type ViewMode = "compact" | "expanded";

const STORAGE_KEY = "customers-view-mode";

function useViewMode() {
  const [mode, setMode] = useState<ViewMode>("compact");

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "compact" || saved === "expanded") setMode(saved);
  }, []);

  const toggle = useCallback(() => {
    setMode((prev) => {
      const next = prev === "compact" ? "expanded" : "compact";
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  return { mode, toggle };
}

interface Props {
  initialData: CustomerListItem[];
  initialTotal: number;
  initialSearch?: string;
  initialStatus?: string;
  initialPage?: number;
  orgId: string;
  financials?: Map<string, CustomerFinancials>;
}

const PAGE_SIZE = 50;

const STATUS_OPTIONS = [
  { value: "all", label: "Все статусы" },
  { value: "active", label: "Активные" },
  { value: "inactive", label: "Неактивные" },
] as const;

function formatUsd(n: number): string {
  if (!n) return "—";
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 0 }) + " $";
}

export function CustomersTable({
  initialData,
  initialTotal,
  initialSearch = "",
  initialStatus = "",
  initialPage = 1,
  orgId,
  financials,
}: Props) {
  const getLabel = (v: string) =>
    STATUS_OPTIONS.find((o) => o.value === v)?.label ?? "Все статусы";
  const [statusLabel, setStatusLabel] = useState(getLabel(initialStatus || "all"));
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const { mode, toggle } = useViewMode();
  const totalPages = Math.ceil(initialTotal / PAGE_SIZE);
  const isExpanded = mode === "expanded";

  function formatDate(dateStr: string | null) {
    if (!dateStr) return "—";
    return new Date(dateStr).toLocaleDateString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  }

  function truncate(str: string, max: number) {
    return str.length > max ? str.slice(0, max) + "..." : str;
  }

  const colSpan = isExpanded ? 9 : 2;

  return (
    <div className="space-y-4">
      {/* Search + Filter bar */}
      <form className="flex items-center gap-3" method="GET">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle" size={16} />
          <Input
            name="q"
            defaultValue={initialSearch}
            placeholder="Поиск по названию или ИНН..."
            className="pl-9"
          />
        </div>
        <Select
          name="status"
          defaultValue={initialStatus || "all"}
          onValueChange={(v) => setStatusLabel(getLabel(v ?? "all"))}
        >
          <SelectTrigger className="w-[160px]">
            <span className="flex flex-1 text-left">{statusLabel}</span>
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="submit" size="sm" variant="outline">
          <Search size={16} />
          Найти
        </Button>

        <Toggle
          pressed={isExpanded}
          onPressedChange={toggle}
          size="sm"
          aria-label="Переключить вид"
          className="ml-2"
        >
          {isExpanded ? <LayoutGrid size={16} /> : <List size={16} />}
        </Toggle>

        <Button
          size="sm"
          className="ml-auto bg-accent text-white hover:bg-accent-hover"
          onClick={() => setCreateDialogOpen(true)}
        >
          <Plus size={16} />
          Новый клиент
        </Button>
      </form>

      {/* Stats row */}
      <div className="flex gap-4 text-sm text-text-muted">
        <span>Всего: {initialTotal}</span>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className={isExpanded ? "w-[30%]" : "w-[60%]"}>Наименование</TableHead>
            <TableHead>ИНН</TableHead>
            {isExpanded && (
              <>
                <TableHead>Менеджер</TableHead>
                <TableHead className="text-center">КП</TableHead>
                <TableHead>Посл. КП</TableHead>
                <TableHead>Статус</TableHead>
                <TableHead className="text-right">Выручка</TableHead>
                <TableHead className="text-center">Спец.</TableHead>
                <TableHead className="text-right">Прибыль</TableHead>
              </>
            )}
          </TableRow>
        </TableHeader>
        <TableBody>
          {initialData.map((customer) => {
            const fin = financials?.get(customer.id);
            return (
              <TableRow key={customer.id}>
                <TableCell>
                  <Link
                    href={`/customers/${customer.id}`}
                    className="text-accent hover:underline font-medium"
                  >
                    {truncate(customer.name, isExpanded ? 40 : 60)}
                  </Link>
                </TableCell>
                <TableCell className="text-text-muted tabular-nums">
                  {customer.inn ?? "—"}
                </TableCell>
                {isExpanded && (
                  <>
                    <TableCell className="text-text-muted">
                      {customer.manager?.full_name ?? "—"}
                    </TableCell>
                    <TableCell className="text-center tabular-nums">
                      {fin?.quotes_count ?? customer.quotes_count ?? "—"}
                    </TableCell>
                    <TableCell className="text-text-muted">
                      {formatDate(fin?.last_quote_date ?? customer.last_quote_date)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={customer.status === "active" ? "default" : "secondary"}>
                        {customer.status === "active" ? "Активен" : "Неактивен"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatUsd(fin?.revenue_usd ?? 0)}
                    </TableCell>
                    <TableCell className="text-center tabular-nums">
                      {fin?.specs_count ?? 0}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatUsd(fin?.profit_usd ?? 0)}
                    </TableCell>
                  </>
                )}
              </TableRow>
            );
          })}
          {initialData.length === 0 && (
            <TableRow>
              <TableCell colSpan={colSpan} className="text-center py-8 text-text-subtle">
                Клиенты не найдены
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-muted">
            Страница {initialPage} из {totalPages}
          </span>
          <div className="flex gap-2">
            {initialPage > 1 && (
              <Link
                href={`/customers?page=${initialPage - 1}&q=${initialSearch}&status=${initialStatus}`}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                Назад
              </Link>
            )}
            {initialPage < totalPages && (
              <Link
                href={`/customers?page=${initialPage + 1}&q=${initialSearch}&status=${initialStatus}`}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                Вперёд
              </Link>
            )}
          </div>
        </div>
      )}
      <CreateCustomerDialog
        orgId={orgId}
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
    </div>
  );
}
