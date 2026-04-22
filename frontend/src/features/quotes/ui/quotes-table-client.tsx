"use client";

import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DataTable,
  type DataTableColumn,
  type FilterOptions,
} from "@/shared/ui/data-table";
import type { QuoteListItem } from "@/entities/quote";

import { CreateQuoteDialog } from "./create-quote-dialog";
import { useState, useEffect } from "react";

interface QuotesTableClientProps {
  rows: readonly QuoteListItem[];
  total: number;
  page: number;
  pageSize: number;
  filterOptions: {
    customers: { id: string; name: string }[];
    managers: { id: string; full_name: string }[];
    procurementManagers: { id: string; full_name: string }[];
    brands: string[];
    statuses: { value: string; label: string }[];
    participants: {
      sales: { id: string; full_name: string }[];
      procurement: { id: string; full_name: string }[];
      logistics: { id: string; full_name: string }[];
      customs: { id: string; full_name: string }[];
    };
  };
  userRoles: string[];
  userId: string;
  orgId: string;
  actionStatuses: string[];
}

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
    timeZone: "Europe/Moscow",
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

/**
 * Quotes registry table — a thin wrapper around the reusable DataTable
 * that declares column config, filter options, and row grouping.
 */
export function QuotesTableClient({
  rows,
  total,
  page,
  pageSize,
  filterOptions,
  userRoles,
  userId,
  orgId,
  actionStatuses,
}: QuotesTableClientProps) {
  const router = useRouter();

  const canCreate = hasAnyRole(userRoles, CREATE_ROLES);

  // Auto-open create dialog when ?create=true
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      if (params.get("create") === "true") setCreateDialogOpen(true);
    }
  }, []);

  const statusLabelMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of filterOptions.statuses) map.set(s.value, s.label);
    return map;
  }, [filterOptions.statuses]);

  const columns = useMemo<readonly DataTableColumn<QuoteListItem>[]>(
    () => [
      {
        key: "created_at",
        label: "Дата",
        accessor: (q) => (
          <span className="text-muted-foreground tabular-nums">
            {formatDate(q.created_at)}
          </span>
        ),
        sortable: true,
        width: "110px",
      },
      {
        key: "idn_quote",
        label: "№КП",
        accessor: (q) => (
          <span className="text-accent font-medium">{q.idn_quote}</span>
        ),
        width: "130px",
        alwaysVisible: true,
      },
      {
        key: "customer",
        label: "Клиент",
        accessor: (q) =>
          q.customer ? (
            <button
              type="button"
              className="text-accent hover:underline text-left truncate block max-w-full"
              title={q.customer.name}
              onClick={(e) => {
                e.stopPropagation();
                router.push(`/customers/${q.customer!.id}`);
              }}
            >
              {q.customer.name}
            </button>
          ) : (
            <span className="text-muted-foreground">&mdash;</span>
          ),
        width: "200px",
        filter: { kind: "multi-select" },
      },
      {
        key: "brand",
        label: "Бренды",
        accessor: (q) => (
          <span
            className="text-muted-foreground truncate block"
            title={q.brands.join(", ")}
          >
            {q.brands.length > 0 ? q.brands.join(", ") : "\u2014"}
          </span>
        ),
        width: "140px",
        filter: { kind: "multi-select" },
      },
      {
        key: "status",
        label: "Статус",
        accessor: (q) => (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
            {statusLabelMap.get(q.workflow_status) ?? q.workflow_status}
          </span>
        ),
        sortKey: "workflow_status",
        width: "140px",
        filter: { kind: "multi-select" },
      },
      {
        key: "participants",
        label: "Участники",
        accessor: (q) => {
          // Vertical stack: МОП / МОЗ / МОЛ / МОТ — skip empty roles.
          const rows: { roleLabel: string; name: string }[] = [];
          if (q.manager) rows.push({ roleLabel: "МОП", name: q.manager.full_name });
          if (q.procurement_managers.length > 0) {
            rows.push({
              roleLabel: "МОЗ",
              name: q.procurement_managers.map((m) => m.full_name).join(", "),
            });
          }
          if (q.logistics_user) rows.push({ roleLabel: "МОЛ", name: q.logistics_user.full_name });
          if (q.customs_user) rows.push({ roleLabel: "МОТ", name: q.customs_user.full_name });

          if (rows.length === 0) {
            return <span className="text-muted-foreground">&mdash;</span>;
          }

          return (
            <div className="flex flex-col gap-0.5 text-xs leading-tight">
              {rows.map((r, idx) => (
                <div key={idx} className="flex items-baseline gap-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground shrink-0 w-8">
                    {r.roleLabel}
                  </span>
                  <span className="text-foreground truncate" title={r.name}>
                    {r.name}
                  </span>
                </div>
              ))}
            </div>
          );
        },
        width: "300px",
        filter: {
          kind: "grouped-multi-select",
          groups: {
            sales: "МОП",
            procurement: "МОЗ",
            logistics: "МОЛ",
            customs: "МОТ",
          },
        },
      },
      {
        key: "version",
        label: "Версия",
        accessor: (q) =>
          q.version_count > 1 ? (
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
              v{q.current_version} ({q.version_count})
            </span>
          ) : (
            <span className="text-muted-foreground text-sm">
              v{q.current_version}
            </span>
          ),
        align: "center",
        width: "90px",
      },
      {
        key: "amount",
        label: "Сумма",
        accessor: (q) => (
          <span className="text-right tabular-nums block">
            {formatAmount(q.total_amount_quote, q.currency)}
          </span>
        ),
        sortable: true,
        sortKey: "amount",
        align: "right",
        filter: { kind: "range" },
        width: "140px",
      },
      {
        key: "profit",
        label: "Прибыль",
        accessor: (q) => {
          const profit = formatProfit(q.total_profit_usd);
          return (
            <span className={`text-right tabular-nums block ${profit.className}`}>
              {profit.text}
            </span>
          );
        },
        align: "right",
        width: "120px",
      },
    ],
    [router, statusLabelMap]
  );

  // Build filter options keyed by column key for the DataTable
  const filterOptionsMap: FilterOptions = useMemo(() => {
    // Participants: flat list of options with composite values + group tags.
    const participantOptions = [
      ...filterOptions.participants.sales.map((u) => ({
        value: `sales:${u.id}`,
        label: u.full_name,
        group: "sales",
      })),
      ...filterOptions.participants.procurement.map((u) => ({
        value: `procurement:${u.id}`,
        label: u.full_name,
        group: "procurement",
      })),
      ...filterOptions.participants.logistics.map((u) => ({
        value: `logistics:${u.id}`,
        label: u.full_name,
        group: "logistics",
      })),
      ...filterOptions.participants.customs.map((u) => ({
        value: `customs:${u.id}`,
        label: u.full_name,
        group: "customs",
      })),
    ];

    return {
      customer: filterOptions.customers.map((c) => ({
        value: c.id,
        label: c.name,
      })),
      brand: filterOptions.brands.map((b) => ({ value: b, label: b })),
      status: filterOptions.statuses,
      participants: participantOptions,
    };
  }, [filterOptions]);

  const actionStatusSet = useMemo(
    () => new Set(actionStatuses),
    [actionStatuses]
  );

  function handleRowClick(quote: QuoteListItem) {
    router.push(`/quotes/${quote.id}`);
  }

  return (
    <>
      <DataTable<QuoteListItem>
        tableKey="quotes"
        rows={rows}
        total={total}
        page={page}
        pageSize={pageSize}
        rowKey={(q) => q.id}
        columns={columns}
        filterOptions={filterOptionsMap}
        onRowClick={handleRowClick}
        search={{
          placeholder: "Поиск по КП, клиенту, бренду...",
        }}
        rowGrouping={{
          label: "Требует вашего действия",
          predicate: (q) => actionStatusSet.has(q.workflow_status),
        }}
        topBarActions={
          canCreate ? (
            <Button
              type="button"
              size="sm"
              className="bg-accent text-white hover:bg-accent-hover"
              onClick={() => setCreateDialogOpen(true)}
            >
              <Plus size={16} />
              Новый КП
            </Button>
          ) : null
        }
        emptyState={<p>Нет коммерческих предложений</p>}
        viewsEnabled={true}
        currentUserId={userId}
        basePath="/quotes"
      />

      {canCreate && (
        <CreateQuoteDialog
          orgId={orgId}
          userId={userId}
          open={createDialogOpen}
          onOpenChange={setCreateDialogOpen}
        />
      )}
    </>
  );
}
