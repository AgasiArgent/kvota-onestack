"use client";

import { useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CreateSupplierDialog } from "./create-supplier-dialog";
import { SuppliersFilterBar } from "./suppliers-filter-bar";
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
  SupplierFilterOptions,
} from "@/entities/supplier";

interface Props {
  initialData: SupplierListItem[];
  initialTotal: number;
  activeCount: number;
  inactiveCount: number;
  initialSearch?: string;
  initialCountry?: string;
  initialStatus?: string;
  initialAssignee?: string;
  initialBrand?: string;
  initialPage?: number;
  filterOptions: SupplierFilterOptions;
  orgId: string;
}

const PAGE_SIZE = 50;

export function SuppliersTable({
  initialData,
  initialTotal,
  activeCount,
  inactiveCount,
  initialSearch = "",
  initialCountry = "",
  initialStatus = "",
  initialAssignee = "",
  initialBrand = "",
  initialPage = 1,
  filterOptions,
  orgId,
}: Props) {
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const { searchParams } = useFilterNavigation();
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

  // Per-КПП totals are converted to USD via historical FX (kvota.exchange_rates
  // looked up by the КПП's created_at), then summed and rounded to integer USD.
  // See entities/supplier/lib/historical-fx.ts for the conversion logic.
  function formatTotalUsd(value: number | null): string {
    if (value == null) return "—";
    return `$${new Intl.NumberFormat("en-US", {
      maximumFractionDigits: 0,
    }).format(value)}`;
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
      {/* Search + Страна/МОЗ/Бренд/Статус filters (Testing 2 row 92) */}
      <div className="flex items-start gap-3">
        <div className="flex-1">
          <SuppliersFilterBar
            search={initialSearch}
            country={initialCountry}
            assignee={initialAssignee}
            brand={initialBrand}
            status={initialStatus}
            options={filterOptions}
          />
        </div>
        <Button
          size="sm"
          className="shrink-0 bg-accent text-white hover:bg-accent-hover"
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
                {formatTotalUsd(supplier.invoice_total_usd)}
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
