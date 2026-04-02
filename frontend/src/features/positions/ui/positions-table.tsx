"use client";

import { useState, useRef } from "react";
import { ChevronRight, ChevronDown, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
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
import { Pagination } from "@/shared/ui/pagination";
import { useFilterNavigation } from "@/shared/lib/use-filter-navigation";
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
  initialSearch: string;
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
  initialSearch,
  initialBrand,
  initialMozId,
  initialAvailability,
  initialDateFrom,
  initialDateTo,
  initialPage,
}: Props) {
  const [searchValue, setSearchValue] = useState(initialSearch);
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
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const { navigate, searchParams } = useFilterNavigation();

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

  function handleAvailabilityChange(value: string | null) {
    const v = value ?? "all";
    setAvailabilityLabel(getAvailabilityLabel(v));
    navigate({ availability: v });
  }

  function handleBrandChange(value: string | null) {
    const v = value ?? "all";
    setBrandLabel(getBrandLabel(v));
    navigate({ brand: v });
  }

  function handleMozChange(value: string | null) {
    const v = value ?? "all";
    setMozLabel(getMozLabel(v));
    navigate({ moz: v });
  }

  function handleSearchChange(value: string) {
    setSearchValue(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      navigate({ search: value || undefined });
    }, 300);
  }

  function handleDateChange(field: "dateFrom" | "dateTo", value: string) {
    clearTimeout(debounceRef.current);
    navigate({ [field]: value || undefined });
  }

  function buildPaginationHref(page: number): string {
    const params = new URLSearchParams(searchParams?.toString() ?? "");
    if (page > 1) {
      params.set("page", String(page));
    } else {
      params.delete("page");
    }
    return `/positions?${params.toString()}`;
  }

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle" size={16} />
          <Input
            value={searchValue}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Поиск по артикулу..."
            className="pl-9 w-[200px]"
          />
        </div>

        <Select
          defaultValue={initialAvailability || "all"}
          onValueChange={handleAvailabilityChange}
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
          defaultValue={initialBrand || "all"}
          onValueChange={handleBrandChange}
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
          defaultValue={initialMozId || "all"}
          onValueChange={handleMozChange}
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
          type="date"
          defaultValue={initialDateFrom}
          className="w-[150px]"
          placeholder="С"
          onChange={(e) => handleDateChange("dateFrom", e.target.value)}
        />
        <Input
          type="date"
          defaultValue={initialDateTo}
          className="w-[150px]"
          placeholder="По"
          onChange={(e) => handleDateChange("dateTo", e.target.value)}
        />
      </div>

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
            const key = `${product.brand}::${product.productCode}`;
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
      <Pagination
        currentPage={initialPage}
        totalPages={totalPages}
        totalItems={total}
        itemLabel="позиций"
        buildHref={buildPaginationHref}
      />
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
          {product.productCode || "—"}
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
