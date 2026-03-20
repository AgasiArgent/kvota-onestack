"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Search, Plus, FileSpreadsheet } from "lucide-react";
import { Toaster } from "sonner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
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
  PhmbQuoteListItem,
  PhmbQuoteStatus,
  PhmbDefaults,
  SellerCompany,
} from "@/entities/phmb-quote/types";
import { CreatePhmbDialog } from "./create-phmb-dialog";

interface PhmbRegistryProps {
  quotes: PhmbQuoteListItem[];
  total: number;
  defaults: PhmbDefaults;
  sellerCompanies: SellerCompany[];
  orgId: string;
  userId: string;
  initialSearch?: string;
  initialStatus?: PhmbQuoteStatus;
  initialPage?: number;
}

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: "all", label: "Все статусы" },
  { value: "draft", label: "Черновик" },
  { value: "waiting_prices", label: "Ожидает цен" },
  { value: "ready", label: "Готов" },
] as const;

const STATUS_BADGE: Record<
  PhmbQuoteStatus,
  { label: string; className: string }
> = {
  draft: {
    label: "Черновик",
    className: "bg-secondary text-secondary-foreground",
  },
  waiting_prices: {
    label: "Ожидает цен",
    className: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
  },
  ready: {
    label: "Готов",
    className: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  },
};

function formatDate(dateStr: string | null) {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatAmount(amount: number | null) {
  if (amount === null || amount === 0) return "\u2014";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function PhmbRegistry({
  quotes,
  total,
  defaults,
  sellerCompanies,
  orgId,
  userId,
  initialSearch = "",
  initialStatus,
  initialPage = 1,
}: PhmbRegistryProps) {
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [searchValue, setSearchValue] = useState(initialSearch);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const { navigate, searchParams } = useFilterNavigation();

  const totalPages = Math.ceil(total / PAGE_SIZE);

  function handleSearchChange(value: string) {
    setSearchValue(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      navigate({ search: value || undefined });
    }, 300);
  }

  function handleStatusChange(value: string | null) {
    navigate({ status: value ?? "all" });
  }

  function handleRowClick(id: string) {
    router.push(`/phmb/${id}`);
  }

  const buildPaginationHref = useCallback(
    (page: number): string => {
      const params = new URLSearchParams(searchParams?.toString() ?? "");
      if (page > 1) {
        params.set("page", String(page));
      } else {
        params.delete("page");
      }
      return `/phmb?${params.toString()}`;
    },
    [searchParams]
  );

  const isEmpty = quotes.length === 0 && !initialSearch && !initialStatus;

  if (isEmpty) {
    return (
      <div>
        <Toaster position="top-right" richColors />
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <FileSpreadsheet
            size={48}
            className="text-text-subtle mb-4"
            strokeWidth={1.5}
          />
          <h2 className="text-lg font-semibold mb-2">
            Нет КП по прайсу
          </h2>
          <p className="text-text-muted text-sm mb-6 max-w-md">
            Создайте первое коммерческое предложение на основе прайс-листа
            с автоматическим расчётом наценки
          </p>
          <Button
            onClick={() => setDialogOpen(true)}
            className="bg-accent text-white hover:bg-accent-hover"
          >
            <Plus size={16} />
            Создать первое КП
          </Button>
        </div>
        <CreatePhmbDialog
          defaults={defaults}
          sellerCompanies={sellerCompanies}
          orgId={orgId}
          userId={userId}
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Toaster position="top-right" richColors />

      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">PHMB</h1>
        <Button
          onClick={() => setDialogOpen(true)}
          className="bg-accent text-white hover:bg-accent-hover"
          size="sm"
        >
          <Plus size={16} />
          Создать КП
        </Button>
      </div>

      {/* Search + Filter bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle"
            size={16}
          />
          <Input
            value={searchValue}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Поиск по клиенту или IDN..."
            className="pl-9"
          />
        </div>
        <Select
          value={initialStatus ?? "all"}
          onValueChange={handleStatusChange}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Все статусы" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Stats row */}
      <div className="text-sm text-text-muted">Всего: {total}</div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[120px]">Дата</TableHead>
            <TableHead className="w-[140px]">IDN</TableHead>
            <TableHead>Клиент</TableHead>
            <TableHead className="text-center w-[100px]">Позиции</TableHead>
            <TableHead className="text-right w-[120px] hidden md:table-cell">
              Сумма
            </TableHead>
            <TableHead className="w-[140px]">Статус</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {quotes.map((quote) => {
            const badge = STATUS_BADGE[quote.status];
            return (
              <TableRow
                key={quote.id}
                className="cursor-pointer"
                onClick={() => handleRowClick(quote.id)}
              >
                <TableCell className="text-text-muted tabular-nums">
                  {formatDate(quote.created_at)}
                </TableCell>
                <TableCell className="font-medium text-accent">
                  {quote.idn_quote}
                </TableCell>
                <TableCell>{quote.customer_name}</TableCell>
                <TableCell className="text-center tabular-nums">
                  {quote.items_priced}/{quote.items_total}
                </TableCell>
                <TableCell className="text-right tabular-nums hidden md:table-cell">
                  {formatAmount(quote.total_amount_usd)}
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className={badge.className}>
                    {badge.label}
                  </Badge>
                </TableCell>
              </TableRow>
            );
          })}
          {quotes.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={6}
                className="text-center py-8 text-text-subtle"
              >
                Ничего не найдено
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      <Pagination
        currentPage={initialPage}
        totalPages={totalPages}
        totalItems={total}
        itemLabel="КП"
        buildHref={buildPaginationHref}
      />

      {/* Create dialog */}
      <CreatePhmbDialog
        defaults={defaults}
        sellerCompanies={sellerCompanies}
        orgId={orgId}
        userId={userId}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />
    </div>
  );
}
