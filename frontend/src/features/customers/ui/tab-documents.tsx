"use client";

import { useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";

interface Quote {
  id: string;
  idn: string;
  total_amount: number | null;
  profit_amount: number | null;
  created_at: string | null;
  status: string;
}

interface Spec {
  id: string;
  idn: string | null;
  total_amount: number | null;
  profit_amount: number | null;
  created_at: string | null;
  status: string;
}

interface Props {
  quotes: Quote[];
  specs: Spec[];
  initialSubTab?: string;
}

type SubTab = "quotes" | "specs";

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: "quotes", label: "КП" },
  { key: "specs", label: "Спецификации" },
];

const STATUS_LABELS: Record<string, string> = {
  draft: "Черновик",
  calculating: "Расчёт",
  calculated: "Рассчитан",
  in_review: "На проверке",
  approved: "Одобрен",
  rejected: "Отклонён",
  cancelled: "Отменён",
  signed: "Подписана",
  active: "Активна",
  completed: "Завершена",
};

export function TabDocuments({ quotes, specs, initialSubTab }: Props) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>(
    (initialSubTab as SubTab) ?? "quotes"
  );

  function formatDate(d: string | null) {
    if (!d) return "—";
    return new Date(d).toLocaleDateString("ru-RU");
  }

  function formatAmount(n: number | null) {
    if (n == null) return "—";
    return `$${n.toLocaleString("ru-RU")}`;
  }

  return (
    <div>
      <div className="flex gap-2 mb-6">
        {SUB_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSubTab(tab.key)}
            className={cn(
              "px-3 py-1.5 text-sm rounded-md transition-colors",
              activeSubTab === tab.key
                ? "bg-accent-subtle text-accent font-medium"
                : "text-text-muted hover:bg-sidebar"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeSubTab === "quotes" && (
        <DocumentTable
          items={quotes}
          emptyText="Нет КП"
          linkPrefix="/quotes"
          formatDate={formatDate}
          formatAmount={formatAmount}
        />
      )}
      {activeSubTab === "specs" && (
        <DocumentTable
          items={specs}
          emptyText="Нет спецификаций"
          linkPrefix="/specifications"
          formatDate={formatDate}
          formatAmount={formatAmount}
        />
      )}
    </div>
  );
}

function DocumentTable({
  items,
  emptyText,
  linkPrefix,
  formatDate,
  formatAmount,
}: {
  items: { id: string; idn: string | null; total_amount: number | null; profit_amount: number | null; created_at: string | null; status: string }[];
  emptyText: string;
  linkPrefix: string;
  formatDate: (d: string | null) => string;
  formatAmount: (n: number | null) => string;
}) {
  if (items.length === 0) {
    return <p className="py-8 text-center text-text-subtle">{emptyText}</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>№</TableHead>
          <TableHead>Сумма</TableHead>
          <TableHead>Профит</TableHead>
          <TableHead>Дата</TableHead>
          <TableHead>Статус</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => (
          <TableRow key={item.id}>
            <TableCell>
              <Link
                href={`${linkPrefix}/${item.id}`}
                className="text-accent hover:underline font-medium"
              >
                {item.idn}
              </Link>
            </TableCell>
            <TableCell className="tabular-nums">{formatAmount(item.total_amount)}</TableCell>
            <TableCell className="tabular-nums">{formatAmount(item.profit_amount)}</TableCell>
            <TableCell className="text-text-muted">{formatDate(item.created_at)}</TableCell>
            <TableCell>
              <Badge variant="secondary">{STATUS_LABELS[item.status] ?? item.status}</Badge>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
