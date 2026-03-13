"use client";

import Link from "next/link";
import { Search, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
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
import type { CustomerListItem } from "@/entities/customer";

interface Props {
  initialData: CustomerListItem[];
  initialTotal: number;
  initialSearch?: string;
  initialStatus?: string;
  initialPage?: number;
}

const PAGE_SIZE = 50;

export function CustomersTable({
  initialData,
  initialTotal,
  initialSearch = "",
  initialStatus = "",
  initialPage = 1,
}: Props) {
  const totalPages = Math.ceil(initialTotal / PAGE_SIZE);

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

  return (
    <div className="space-y-4">
      {/* Search + Filter bar */}
      <form className="flex items-center gap-3" method="GET">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
          <Input
            name="q"
            defaultValue={initialSearch}
            placeholder="Поиск по названию или ИНН..."
            className="pl-9"
          />
        </div>
        <Select name="status" defaultValue={initialStatus || "all"}>
          <SelectTrigger className="w-[160px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все статусы</SelectItem>
            <SelectItem value="active">Активные</SelectItem>
            <SelectItem value="inactive">Неактивные</SelectItem>
          </SelectContent>
        </Select>
        <Button type="submit" size="sm">
          <Search size={16} />
          Найти
        </Button>
        <Link href="/customers/new" className={buttonVariants({ variant: "default", size: "sm", className: "ml-auto" })}>
          <Plus size={16} />
          Новый клиент
        </Link>
      </form>

      {/* Stats row */}
      <div className="flex gap-4 text-sm text-slate-500">
        <span>Всего: {initialTotal}</span>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40%]">Наименование</TableHead>
            <TableHead>ИНН</TableHead>
            <TableHead>Менеджер</TableHead>
            <TableHead className="text-center">КП</TableHead>
            <TableHead>Посл. КП</TableHead>
            <TableHead>Статус</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {initialData.map((customer) => (
            <TableRow key={customer.id}>
              <TableCell>
                <Link
                  href={`/customers/${customer.id}`}
                  className="text-blue-600 hover:underline font-medium"
                >
                  {truncate(customer.name, 50)}
                </Link>
              </TableCell>
              <TableCell className="text-slate-500 tabular-nums">
                {customer.inn ?? "—"}
              </TableCell>
              <TableCell className="text-slate-500">
                {customer.manager?.full_name ?? "—"}
              </TableCell>
              <TableCell className="text-center tabular-nums">
                {customer.quotes_count || "—"}
              </TableCell>
              <TableCell className="text-slate-500">
                {formatDate(customer.last_quote_date)}
              </TableCell>
              <TableCell>
                <Badge variant={customer.status === "active" ? "default" : "secondary"}>
                  {customer.status === "active" ? "Активен" : "Неактивен"}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
          {initialData.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-8 text-slate-400">
                Клиенты не найдены
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-500">
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
    </div>
  );
}
