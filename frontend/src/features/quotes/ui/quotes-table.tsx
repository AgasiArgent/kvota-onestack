"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, Plus } from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { StatusGroupFilter } from "./status-group-filter";
import { CreateQuoteDialog } from "./create-quote-dialog";
import type { QuoteListItem, QuotesFilterParams } from "@/entities/quote/types";
import { getGroupForStatus } from "@/entities/quote/types";

interface QuotesTableProps {
  actionQuotes: QuoteListItem[];
  otherQuotes: QuoteListItem[];
  total: number;
  page: number;
  pageSize: number;
  filters: QuotesFilterParams;
  customers: { id: string; name: string }[];
  managers: { id: string; full_name: string }[];
  userRoles: string[];
  userId: string;
  orgId: string;
}

const ADMIN_ROLES = ["admin", "top_manager", "head_of_sales"];
const CREATE_ROLES = ["sales", "head_of_sales", "admin"];

function hasAnyRole(userRoles: string[], allowedRoles: string[]): boolean {
  return userRoles.some((r) => allowedRoles.includes(r));
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function formatAmount(
  amount: number | null,
  currency: string | null
): string {
  if (amount === null || amount === undefined) return "\u2014";
  return new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: currency ?? "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatProfit(profit: number | null): {
  text: string;
  className: string;
} {
  if (profit === null || profit === undefined || profit === 0) {
    return { text: "\u2014", className: "text-muted-foreground" };
  }
  const text = new Intl.NumberFormat("ru-RU", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(profit);
  if (profit > 0) return { text, className: "text-green-600" };
  return { text, className: "text-red-600" };
}

function buildFilterUrl(
  baseFilters: QuotesFilterParams,
  overrides: Partial<QuotesFilterParams>
): string {
  const merged = { ...baseFilters, ...overrides };
  const params = new URLSearchParams();
  if (merged.status) params.set("status", merged.status);
  if (merged.customer) params.set("customer", merged.customer);
  if (merged.manager) params.set("manager", merged.manager);
  if (merged.page && merged.page > 1) params.set("page", String(merged.page));
  const qs = params.toString();
  return qs ? `/quotes?${qs}` : "/quotes";
}

function QuoteRow({
  quote,
  onRowClick,
  onCustomerClick,
}: {
  quote: QuoteListItem;
  onRowClick: (id: string) => void;
  onCustomerClick: (e: React.MouseEvent, id: string) => void;
}) {
  const group = getGroupForStatus(quote.workflow_status);
  const profit = formatProfit(quote.total_profit_usd);
  return (
    <TableRow
      className="cursor-pointer"
      onClick={() => onRowClick(quote.id)}
    >
      <TableCell className="text-muted-foreground tabular-nums">
        {formatDate(quote.created_at)}
      </TableCell>
      <TableCell>
        <span className="text-accent font-medium">
          {quote.idn_quote}
        </span>
      </TableCell>
      <TableCell className="max-w-[200px]">
        {quote.customer ? (
          <button
            type="button"
            className="text-accent hover:underline text-left truncate block max-w-full"
            title={quote.customer.name}
            onClick={(e) => onCustomerClick(e, quote.customer!.id)}
          >
            {quote.customer.name}
          </button>
        ) : (
          <span className="text-muted-foreground">&mdash;</span>
        )}
      </TableCell>
      <TableCell className="text-muted-foreground truncate max-w-[140px]" title={quote.manager?.full_name ?? ""}>
        {quote.manager?.full_name ?? "\u2014"}
      </TableCell>
      <TableCell>
        {group ? (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${group.color}`}
          >
            {group.label}
          </span>
        ) : (
          <span className="text-muted-foreground text-xs">
            {quote.workflow_status}
          </span>
        )}
      </TableCell>
      <TableCell className="text-center tabular-nums">
        {quote.version_count > 1 ? (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
            v{quote.current_version} ({quote.version_count})
          </span>
        ) : (
          <span className="text-muted-foreground text-sm">
            v{quote.current_version}
          </span>
        )}
      </TableCell>
      <TableCell className="text-right tabular-nums">
        {formatAmount(quote.total_amount_quote, quote.currency)}
      </TableCell>
      <TableCell className={`text-right tabular-nums ${profit.className}`}>
        {profit.text}
      </TableCell>
    </TableRow>
  );
}

export function QuotesTable({
  actionQuotes,
  otherQuotes,
  total,
  page,
  pageSize,
  filters,
  customers,
  managers,
  userRoles,
  userId,
  orgId,
}: QuotesTableProps) {
  const router = useRouter();
  const [createDialogOpen, setCreateDialogOpen] = useState(false);

  const canCreate = hasAnyRole(userRoles, CREATE_ROLES);
  const canFilterByManager = hasAnyRole(userRoles, ADMIN_ROLES);
  const totalPages = Math.ceil(total / pageSize);

  // Parse active group vs individual status
  const activeGroup = filters.status ?? null;
  const isIndividualStatus =
    activeGroup !== null &&
    getGroupForStatus(activeGroup) !== undefined &&
    !["draft", "in_progress", "approval", "deal", "closed"].includes(
      activeGroup
    );

  const resolvedActiveGroup = isIndividualStatus
    ? getGroupForStatus(activeGroup!)?.key ?? null
    : activeGroup;
  const resolvedActiveStatus = isIndividualStatus ? activeGroup : null;

  // Customer filter label
  const getCustomerLabel = (id: string) =>
    customers.find((c) => c.id === id)?.name ?? "Все клиенты";
  const [customerLabel, setCustomerLabel] = useState(
    filters.customer ? getCustomerLabel(filters.customer) : "Все клиенты"
  );

  // Manager filter label
  const getManagerLabel = (id: string) =>
    managers.find((m) => m.id === id)?.full_name ?? "Все менеджеры";
  const [managerLabel, setManagerLabel] = useState(
    filters.manager ? getManagerLabel(filters.manager) : "Все менеджеры"
  );

  function handleRowClick(quoteId: string) {
    // Quote detail page is still in FastHTML — navigate to legacy app
    // TODO: Change to router.push() when /quotes/[id] is migrated to Next.js
    window.location.href = `https://kvotaflow.ru/quotes/${quoteId}`;
  }

  function handleCustomerClick(
    e: React.MouseEvent,
    customerId: string
  ) {
    e.stopPropagation();
    router.push(`/customers/${customerId}`);
  }

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <form className="space-y-3" method="GET" action="/quotes">
        {/* Status group pills */}
        <StatusGroupFilter
          activeGroup={resolvedActiveGroup}
          activeStatus={resolvedActiveStatus}
        />

        {/* Dropdown filters row */}
        <div className="flex items-center gap-3">
          <Select
            name="customer"
            defaultValue={filters.customer ?? "all"}
            onValueChange={(v) => setCustomerLabel(!v || v === "all" ? "Все клиенты" : getCustomerLabel(v))}
          >
            <SelectTrigger className="w-[220px]">
              <span className="flex flex-1 text-left truncate">{customerLabel}</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все клиенты</SelectItem>
              {customers.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {canFilterByManager && (
            <Select
              name="manager"
              defaultValue={filters.manager ?? "all"}
              onValueChange={(v) => setManagerLabel(!v || v === "all" ? "Все менеджеры" : getManagerLabel(v))}
            >
              <SelectTrigger className="w-[200px]">
                <span className="flex flex-1 text-left truncate">{managerLabel}</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Все менеджеры</SelectItem>
                {managers.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <Button type="submit" size="sm" variant="outline">
            Применить
          </Button>

          {canCreate && (
            <Button
              type="button"
              size="sm"
              className="ml-auto bg-accent text-white hover:bg-accent-hover"
              onClick={() => setCreateDialogOpen(true)}
            >
              <Plus size={16} />
              Новый КП
            </Button>
          )}
        </div>
      </form>

      {/* Stats row */}
      <div className="flex gap-4 text-sm text-muted-foreground">
        <span>Всего: {total}</span>
      </div>

      {/* Table */}
      <Table className="table-fixed">
        <TableHeader>
          <TableRow>
            <TableHead className="w-[100px]">Дата</TableHead>
            <TableHead className="w-[130px]">№КП</TableHead>
            <TableHead className="w-[200px]">Клиент</TableHead>
            <TableHead className="w-[140px]">Менеджер</TableHead>
            <TableHead className="w-[120px]">Статус</TableHead>
            <TableHead className="text-center">Версия</TableHead>
            <TableHead className="text-right">Сумма</TableHead>
            <TableHead className="text-right">Прибыль</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {actionQuotes.length > 0 && (
            <>
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={8} className="py-3 px-0">
                  <div className="border-l-4 border-accent pl-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                    <AlertCircle size={16} className="text-accent shrink-0" />
                    Требует вашего действия ({actionQuotes.length})
                  </div>
                </TableCell>
              </TableRow>
              {actionQuotes.map((quote) => (
                <QuoteRow
                  key={quote.id}
                  quote={quote}
                  onRowClick={handleRowClick}
                  onCustomerClick={handleCustomerClick}
                />
              ))}
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={8} className="py-2 px-0">
                  <div className="border-t border-border" />
                </TableCell>
              </TableRow>
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={8} className="py-2 px-0">
                  <span className="text-sm text-muted-foreground font-medium">
                    Остальные КП
                  </span>
                </TableCell>
              </TableRow>
            </>
          )}
          {otherQuotes.map((quote) => (
            <QuoteRow
              key={quote.id}
              quote={quote}
              onRowClick={handleRowClick}
              onCustomerClick={handleCustomerClick}
            />
          ))}
          {actionQuotes.length === 0 && otherQuotes.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={8}
                className="text-center py-12 text-muted-foreground"
              >
                <div className="space-y-2">
                  <p>Нет коммерческих предложений</p>
                  {(filters.status || filters.customer || filters.manager) && (
                    <p className="text-sm">
                      Попробуйте{" "}
                      <Link
                        href="/quotes"
                        className="text-accent hover:underline"
                      >
                        сбросить фильтры
                      </Link>
                    </p>
                  )}
                </div>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Страница {page} из {totalPages}
          </span>
          <div className="flex gap-2">
            {page > 1 && (
              <Link
                href={buildFilterUrl(filters, { page: page - 1 })}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                ← Назад
              </Link>
            )}
            {page < totalPages && (
              <Link
                href={buildFilterUrl(filters, { page: page + 1 })}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                Вперёд →
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Create quote dialog */}
      {canCreate && (
        <CreateQuoteDialog
          orgId={orgId}
          userId={userId}
          open={createDialogOpen}
          onOpenChange={setCreateDialogOpen}
        />
      )}
    </div>
  );
}
