"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ExternalLink, Search } from "lucide-react";
import type { FeedbackItem } from "@/entities/admin/types";
import {
  FEEDBACK_TYPE_LABELS,
  FEEDBACK_TYPE_COLORS,
  FEEDBACK_STATUS_LABELS,
  FEEDBACK_STATUS_COLORS,
} from "@/entities/admin/types";

interface FeedbackListProps {
  items: FeedbackItem[];
  total: number;
  page: number;
  pageSize: number;
  activeStatus: string | null;
  searchQuery: string;
}

const STATUS_TABS = [
  { value: null, label: "Все" },
  { value: "new", label: "Новые" },
  { value: "in_progress", label: "В работе" },
  { value: "resolved", label: "Решено" },
  { value: "closed", label: "Закрыто" },
] as const;

function formatDate(dateStr: string): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function buildUrl(status: string | null, search: string, page?: number): string {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (search) params.set("search", search);
  if (page && page > 1) params.set("page", String(page));
  const qs = params.toString();
  return qs ? `/admin/feedback?${qs}` : "/admin/feedback";
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

export function FeedbackList({
  items,
  total,
  page,
  pageSize,
  activeStatus,
  searchQuery,
}: FeedbackListProps) {
  const router = useRouter();
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      {/* Status filter tabs */}
      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => {
          const isActive =
            tab.value === activeStatus ||
            (tab.value === null && !activeStatus);
          return (
            <Link
              key={tab.value ?? "all"}
              href={buildUrl(tab.value, searchQuery)}
              className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-foreground text-background"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {tab.label}
            </Link>
          );
        })}
      </div>

      {/* Search */}
      <form method="GET" action="/admin/feedback" className="flex gap-2 max-w-md">
        {activeStatus && (
          <input type="hidden" name="status" value={activeStatus} />
        )}
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
          <Input
            name="search"
            placeholder="Поиск по описанию, email или ID..."
            defaultValue={searchQuery}
            className="pl-9"
          />
        </div>
        <Button type="submit" variant="outline" size="sm">
          Найти
        </Button>
      </form>

      {/* Stats */}
      <div className="text-sm text-muted-foreground">
        Всего: {total}
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[100px]">ID</TableHead>
            <TableHead className="w-[90px]">Тип</TableHead>
            <TableHead>Описание</TableHead>
            <TableHead className="w-[180px]">Пользователь</TableHead>
            <TableHead className="w-[100px]">Статус</TableHead>
            <TableHead className="w-[90px]">ClickUp</TableHead>
            <TableHead className="w-[100px]">Дата</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const typeColor =
              FEEDBACK_TYPE_COLORS[item.feedback_type] ?? "bg-slate-100 text-slate-700";
            const statusColor =
              FEEDBACK_STATUS_COLORS[item.status] ?? "bg-slate-100 text-slate-700";

            return (
              <TableRow
                key={item.short_id}
                className="cursor-pointer"
                onClick={() => router.push(`/admin/feedback/${item.short_id}`)}
              >
                <TableCell className="font-mono text-xs">
                  {item.short_id}
                </TableCell>
                <TableCell>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${typeColor}`}
                  >
                    {FEEDBACK_TYPE_LABELS[item.feedback_type] ?? item.feedback_type}
                  </span>
                </TableCell>
                <TableCell
                  className="max-w-[300px] truncate"
                  title={item.description}
                >
                  {truncate(item.description, 80)}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground truncate max-w-[180px]">
                  {item.user_email ?? item.user_name ?? "\u2014"}
                </TableCell>
                <TableCell>
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${statusColor}`}
                  >
                    {FEEDBACK_STATUS_LABELS[item.status] ?? item.status}
                  </span>
                </TableCell>
                <TableCell>
                  {item.clickup_task_id ? (
                    <a
                      href={`https://app.clickup.com/t/${item.clickup_task_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent hover:text-accent-hover"
                      onClick={(e) => e.stopPropagation()}
                      title="Открыть в ClickUp"
                    >
                      <ExternalLink size={14} />
                    </a>
                  ) : (
                    <span className="text-muted-foreground">\u2014</span>
                  )}
                </TableCell>
                <TableCell className="text-muted-foreground tabular-nums">
                  {formatDate(item.created_at)}
                </TableCell>
              </TableRow>
            );
          })}
          {items.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={7}
                className="text-center py-12 text-muted-foreground"
              >
                <div className="space-y-2">
                  <p>Нет обращений</p>
                  {(activeStatus || searchQuery) && (
                    <p className="text-sm">
                      Попробуйте{" "}
                      <Link
                        href="/admin/feedback"
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
                href={buildUrl(activeStatus, searchQuery, page - 1)}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                \u2190 Назад
              </Link>
            )}
            {page < totalPages && (
              <Link
                href={buildUrl(activeStatus, searchQuery, page + 1)}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                Вперёд \u2192
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
