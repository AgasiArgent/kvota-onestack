"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronRight, ChevronDown, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ProductListItem, SourcingEntry } from "@/entities/position/types";
import { PositionHistory } from "./position-history";
import { formatDate, formatPrice } from "./format";

interface Props {
  products: ProductListItem[];
  details: Record<string, SourcingEntry[]>;
  total: number;
  filterOptions: {
    brands: string[];
    managers: { id: string; name: string }[];
  };
  initialBrand: string;
  initialMozId: string;
  initialAvailability: string;
  initialDateFrom: string;
  initialDateTo: string;
  initialPage: number;
}

const PAGE_SIZE = 50;

const AVAILABILITY_OPTIONS = [
  { value: "all", label: "Все" },
  { value: "available", label: "Доступен" },
  { value: "unavailable", label: "Недоступен" },
] as const;

export function AvailabilityBadge({ status }: { status: string }) {
  switch (status) {
    case "available":
      return (
        <Badge className="bg-success/10 text-success border-success/20 text-xs">
          Доступен
        </Badge>
      );
    case "unavailable":
      return (
        <Badge variant="destructive" className="text-xs">
          Недоступен
        </Badge>
      );
    case "mixed":
      return (
        <Badge variant="outline" className="text-warning border-warning/30 text-xs">
          Смешанный
        </Badge>
      );
    default:
      return null;
  }
}

export function PositionsTable({
  products,
  details,
  total,
  filterOptions,
  initialBrand,
  initialMozId,
  initialAvailability,
  initialDateFrom,
  initialDateTo,
  initialPage,
}: Props) {
  const [expandedProducts, setExpandedProducts] = useState<Set<string>>(
    new Set()
  );

  const getAvailabilityLabel = (v: string) =>
    AVAILABILITY_OPTIONS.find((o) => o.value === v)?.label ?? "Все";
  const [availabilityLabel, setAvailabilityLabel] = useState(
    getAvailabilityLabel(initialAvailability || "all")
  );

  const getBrandLabel = (v: string) => (v && v !== "all" ? v : "Все бренды");
  const [brandLabel, setBrandLabel] = useState(
    getBrandLabel(initialBrand || "all")
  );

  const getMozLabel = (v: string) => {
    if (!v || v === "all") return "Все МОЗ";
    return filterOptions.managers.find((m) => m.id === v)?.name ?? "Все МОЗ";
  };
  const [mozLabel, setMozLabel] = useState(
    getMozLabel(initialMozId || "all")
  );

  const totalPages = Math.ceil(total / PAGE_SIZE);

  function toggleExpanded(key: string) {
    setExpandedProducts((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function buildQueryString(overrides: Record<string, string | number>) {
    const params = new URLSearchParams();
    const merged = {
      availability: initialAvailability,
      brand: initialBrand,
      moz: initialMozId,
      dateFrom: initialDateFrom,
      dateTo: initialDateTo,
      page: String(initialPage),
      ...Object.fromEntries(
        Object.entries(overrides).map(([k, v]) => [k, String(v)])
      ),
    };
    Object.entries(merged).forEach(([k, v]) => {
      if (v && v !== "all") params.set(k, v);
    });
    return params.toString();
  }

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <form className="flex items-center gap-3 flex-wrap" method="GET">
        <Select
          name="availability"
          defaultValue={initialAvailability || "all"}
          onValueChange={(v) => setAvailabilityLabel(getAvailabilityLabel(v ?? "all"))}
        >
          <SelectTrigger className="w-[150px]">
            <span className="flex flex-1 text-left">{availabilityLabel}</span>
          </SelectTrigger>
          <SelectContent>
            {AVAILABILITY_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          name="brand"
          defaultValue={initialBrand || "all"}
          onValueChange={(v) => setBrandLabel(getBrandLabel(v ?? "all"))}
        >
          <SelectTrigger className="w-[180px]">
            <span className="flex flex-1 text-left truncate">{brandLabel}</span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все бренды</SelectItem>
            {filterOptions.brands.map((b) => (
              <SelectItem key={b} value={b}>
                {b}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          name="moz"
          defaultValue={initialMozId || "all"}
          onValueChange={(v) => setMozLabel(getMozLabel(v ?? "all"))}
        >
          <SelectTrigger className="w-[180px]">
            <span className="flex flex-1 text-left truncate">{mozLabel}</span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все МОЗ</SelectItem>
            {filterOptions.managers.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                {m.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          name="dateFrom"
          type="date"
          defaultValue={initialDateFrom}
          className="w-[150px]"
          placeholder="С"
        />
        <Input
          name="dateTo"
          type="date"
          defaultValue={initialDateTo}
          className="w-[150px]"
          placeholder="По"
        />

        <Button type="submit" size="sm" variant="outline">
          <Search size={16} />
          Найти
        </Button>
      </form>

      {/* Stats */}
      <div className="text-sm text-text-muted">
        Всего: {total}
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[40px]" />
            <TableHead className="w-[110px]">Статус</TableHead>
            <TableHead>Бренд</TableHead>
            <TableHead>Артикул</TableHead>
            <TableHead className="w-[25%]">Наименование</TableHead>
            <TableHead>Цена</TableHead>
            <TableHead>МОЗ</TableHead>
            <TableHead>Дата</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {products.map((product) => {
            const key = `${product.brand}::${product.idnSku}`;
            const isExpanded = expandedProducts.has(key);
            const hasDetails = product.entryCount > 1;
            const entries = details[key] ?? [];

            return (
              <ProductRow
                key={key}
                product={product}
                isExpanded={isExpanded}
                hasDetails={hasDetails}
                entries={entries}
                onToggle={() => toggleExpanded(key)}
              />
            );
          })}
          {products.length === 0 && (
            <tr>
              <td colSpan={8} className="text-center py-8 text-text-subtle">
                Позиции не найдены
              </td>
            </tr>
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-text-muted">
            Страница {initialPage} из {totalPages} | Всего: {total}
          </span>
          <div className="flex gap-2">
            {initialPage > 1 && (
              <Link
                href={`/positions?${buildQueryString({ page: initialPage - 1 })}`}
                className={buttonVariants({ variant: "outline", size: "sm" })}
              >
                Назад
              </Link>
            )}
            {initialPage < totalPages && (
              <Link
                href={`/positions?${buildQueryString({ page: initialPage + 1 })}`}
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

function ProductRow({
  product,
  isExpanded,
  hasDetails,
  entries,
  onToggle,
}: {
  product: ProductListItem;
  isExpanded: boolean;
  hasDetails: boolean;
  entries: SourcingEntry[];
  onToggle: () => void;
}) {
  return (
    <>
      <tr className="border-b border-border-light hover:bg-muted/30">
        {/* Expand chevron */}
        <td className="px-3 py-3">
          {hasDetails ? (
            <button
              onClick={onToggle}
              className="p-1 rounded hover:bg-muted text-text-muted"
              type="button"
              aria-label={isExpanded ? "Свернуть" : "Развернуть"}
            >
              {isExpanded ? (
                <ChevronDown size={16} />
              ) : (
                <ChevronRight size={16} />
              )}
            </button>
          ) : null}
        </td>
        {/* Status */}
        <td className="px-3 py-3">
          <AvailabilityBadge status={product.availabilityStatus} />
        </td>
        {/* Brand */}
        <td className="px-3 py-3 font-medium">{product.brand || "—"}</td>
        {/* SKU */}
        <td className="px-3 py-3 text-text-muted tabular-nums">
          {product.idnSku || "—"}
        </td>
        {/* Product name */}
        <td className="px-3 py-3">{product.productName || "—"}</td>
        {/* Price */}
        <td className="px-3 py-3 tabular-nums">
          {formatPrice(product.latestPrice, product.latestCurrency)}
        </td>
        {/* MOZ */}
        <td className="px-3 py-3 text-text-muted">
          {product.lastMozName ?? "—"}
        </td>
        {/* Date + entry count */}
        <td className="px-3 py-3 tabular-nums text-text-muted">
          <span>{formatDate(product.lastUpdated)}</span>
          {product.entryCount > 1 && (
            <Badge variant="secondary" className="ml-2 text-xs">
              {product.entryCount}
            </Badge>
          )}
        </td>
      </tr>
      {isExpanded && <PositionHistory entries={entries} />}
    </>
  );
}
