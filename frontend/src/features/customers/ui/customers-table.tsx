"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Search, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { Pagination } from "@/shared/ui/pagination";
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
  const router = useRouter();
  const searchParams = useSearchParams();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const getLabel = (v: string) =>
    STATUS_OPTIONS.find((o) => o.value === v)?.label ?? "Все статусы";
  const [statusLabel, setStatusLabel] = useState(getLabel(initialStatus || "all"));
  const [searchValue, setSearchValue] = useState(initialSearch);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const { mode, toggle } = useViewMode();
  const totalPages = Math.ceil(initialTotal / PAGE_SIZE);
  const isExpanded = mode === "expanded";

  function pushParams(overrides: Record<string, string>) {
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    for (const [k, v] of Object.entries(overrides)) {
      if (v && v !== "all") params.set(k, v);
      else params.delete(k);
    }
    params.delete("page"); // reset pagination on filter change
    router.push(`/customers?${params.toString()}`);
  }

  function handleSearchChange(value: string) {
    setSearchValue(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      pushParams({ q: value });
    }, 300);
  }

  function handleStatusChange(value: string | null) {
    const v = value ?? "all";
    setStatusLabel(getLabel(v));
    pushParams({ status: v });
  }

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

  const colSpan = isExpanded ? 10 : 3;

  return (
    <div className="space-y-4">
      {/* Search + Filter bar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle" size={16} />
          <Input
            value={searchValue}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Поиск по названию или ИНН..."
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

        <div className="flex rounded-md border border-border-light overflow-hidden text-sm">
          <button
            onClick={isExpanded ? toggle : undefined}
            className={`px-3 py-1.5 transition-colors ${
              !isExpanded
                ? "bg-accent text-white"
                : "text-text-muted hover:bg-sidebar"
            }`}
          >
            Компакт
          </button>
          <button
            onClick={!isExpanded ? toggle : undefined}
            className={`px-3 py-1.5 transition-colors ${
              isExpanded
                ? "bg-accent text-white"
                : "text-text-muted hover:bg-sidebar"
            }`}
          >
            Подробно
          </button>
        </div>

        <Button
          size="sm"
          className="ml-auto bg-accent text-white hover:bg-accent-hover"
          onClick={() => setCreateDialogOpen(true)}
        >
          <Plus size={16} />
          Новый клиент
        </Button>
      </div>

      {/* Stats row */}
      <div className="flex gap-4 text-sm text-text-muted">
        <span>Всего: {initialTotal}</span>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className={isExpanded ? "w-[30%]" : "w-[50%]"}>Наименование</TableHead>
            <TableHead>ИНН</TableHead>
            <TableHead className="w-[100px]">Дата</TableHead>
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
                <TableCell className="text-text-muted tabular-nums">
                  {formatDate(customer.created_at)}
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
      <Pagination
        currentPage={initialPage}
        totalPages={totalPages}
        totalItems={initialTotal}
        itemLabel="клиентов"
        buildHref={(p) => {
          const params = new URLSearchParams(searchParams?.toString() ?? "");
          if (p > 1) params.set("page", String(p));
          else params.delete("page");
          return `/customers?${params.toString()}`;
        }}
      />
      <CreateCustomerDialog
        orgId={orgId}
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
      />
    </div>
  );
}
