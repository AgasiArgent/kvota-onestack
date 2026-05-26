"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import { Search, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CreateSupplierDialog } from "./create-supplier-dialog";
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
import { Pagination } from "@/shared/ui/pagination";
import { useFilterNavigation } from "@/shared/lib/use-filter-navigation";
import type {
  SupplierListItem,
  SupplierInvoiceTotal,
} from "@/entities/supplier/types";

interface Props {
  initialData: SupplierListItem[];
  initialTotal: number;
  activeCount: number;
  inactiveCount: number;
  initialSearch?: string;
  initialCountry?: string;
  initialStatus?: string;
  initialPage?: number;
  orgId: string;
}

const PAGE_SIZE = 50;

const STATUS_OPTIONS = [
  { value: "all", label: "Все статусы" },
  { value: "active", label: "Активные" },
  { value: "inactive", label: "Неактивные" },
] as const;

export function SuppliersTable({
  initialData,
  initialTotal,
  activeCount,
  inactiveCount,
  initialSearch = "",
  initialCountry = "",
  initialStatus = "",
  initialPage = 1,
  orgId,
}: Props) {
  const getLabel = (v: string) =>
    STATUS_OPTIONS.find((o) => o.value === v)?.label ?? "Все статусы";
  const [statusLabel, setStatusLabel] = useState(getLabel(initialStatus || "all"));
  const [searchValue, setSearchValue] = useState(initialSearch);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const { navigate, searchParams } = useFilterNavigation();
  const totalPages = Math.ceil(initialTotal / PAGE_SIZE);

  function truncate(str: string, max: number) {
    return str.length > max ? str.slice(0, max) + "..." : str;
  }

  // Russian-locale date format (DD.MM.YYYY) — matches the rest of the app.
  const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });

  function formatDate(iso: string | null): string {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return dateFormatter.format(d);
  }

  // Currencies differ across КПП so we render one chip per currency,
  // sorted by amount desc (set in the query). "12 500 EUR · 800 USD".
  function formatTotals(totals: SupplierInvoiceTotal[]): string {
    if (totals.length === 0) return "—";
    return totals
      .map(
        (t) =>
          `${new Intl.NumberFormat("ru-RU", {
            maximumFractionDigits: 2,
          }).format(t.amount)} ${t.currency}`
      )
      .join(" · ");
  }

  function handleSearchChange(value: string) {
    setSearchValue(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      navigate({ q: value || undefined });
    }, 300);
  }

  function handleStatusChange(value: string | null) {
    const v = value ?? "all";
    setStatusLabel(getLabel(v));
    navigate({ status: v });
  }

  function buildPaginationHref(page: number): string {
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    if (page > 1) {
      params.set("page", String(page));
    } else {
      params.delete("page");
    }
    return `/suppliers?${params.toString()}`;
  }

  return (
    <div className="space-y-4">
      {/* Search + Filter bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle" size={16} />
          <Input
            value={searchValue}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Поиск по названию..."
            className="pl-9"
          />
        </div>
        <Select
          defaultValue={initialStatus || "all"}
          onValueChange={handleStatusChange}
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
        <Button
          size="sm"
          className="ml-auto bg-accent text-white hover:bg-accent-hover"
          onClick={() => setCreateDialogOpen(true)}
          type="button"
        >
          <Plus size={16} />
          Добавить
        </Button>
      </div>

      {/* Stats row */}
      <div className="flex gap-4 text-sm text-text-muted">
        <span>Всего: {initialTotal}</span>
        <span>Активные: {activeCount}</span>
        <span>Неактивные: {inactiveCount}</span>
      </div>

      {/* Table — columns per Testing 2 row 84 (РОЗ/СтМОЗ/МОЗ request):
          Наименование · Страна · МОЗ · Дата последнего КПП · Сумма КПП · Статус. */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[28%]">Наименование</TableHead>
            <TableHead>Страна</TableHead>
            <TableHead>МОЗ</TableHead>
            <TableHead>Дата последнего КПП</TableHead>
            <TableHead>Сумма КПП</TableHead>
            <TableHead>Статус</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {initialData.map((supplier) => (
            <TableRow key={supplier.id}>
              <TableCell>
                <Link
                  href={`/suppliers/${supplier.id}`}
                  className="text-accent hover:underline font-medium"
                >
                  {truncate(supplier.name, 50)}
                </Link>
              </TableCell>
              <TableCell className="text-text-muted">
                {supplier.country ?? "—"}
              </TableCell>
              <TableCell className="text-text-muted">
                {supplier.assignee_name ?? "—"}
              </TableCell>
              <TableCell className="text-text-muted tabular-nums">
                {formatDate(supplier.last_invoice_at)}
              </TableCell>
              <TableCell className="text-text-muted tabular-nums">
                {formatTotals(supplier.invoice_totals)}
              </TableCell>
              <TableCell>
                <Badge variant={supplier.is_active ? "default" : "secondary"}>
                  {supplier.is_active ? "Активен" : "Неактивен"}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
          {initialData.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-8 text-text-subtle">
                Поставщики не найдены
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      <Pagination
        currentPage={initialPage}
        totalPages={totalPages}
        totalItems={initialTotal}
        itemLabel="поставщиков"
        buildHref={buildPaginationHref}
      />

      <CreateSupplierDialog
        orgId={orgId}
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
    </div>
  );
}
