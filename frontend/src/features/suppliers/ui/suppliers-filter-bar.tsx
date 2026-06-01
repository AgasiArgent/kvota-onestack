"use client";

import { useMemo } from "react";

import { FilterBar, SearchInputFilter } from "@/shared/ui/filter-bar";
import {
  SearchableCombobox,
  type SearchableComboboxItem,
} from "@/shared/ui/searchable-combobox";
import { useFilterNavigation } from "@/shared/lib/use-filter-navigation";
import type { SupplierFilterOptions } from "@/entities/supplier";

const STATUS_OPTIONS = [
  { id: "active", label: "Активные" },
  { id: "inactive", label: "Неактивные" },
] as const;

interface FilterOption extends SearchableComboboxItem {
  label: string;
}

export interface SuppliersFilterBarProps {
  search: string;
  country: string;
  assignee: string;
  brand: string;
  status: string;
  options: SupplierFilterOptions;
}

/**
 * Search + Страна/МОЗ/Бренд/Статус filter bar for /suppliers (Testing 2 row 92).
 *
 * Every dropdown is searchable per the project-wide UI standard (CLAUDE.md):
 * country and brand lists grow unboundedly, so a plain `<select>` is unusable.
 * All filters are URL-backed and applied at the query level so they narrow
 * ACROSS pages, combining with AND semantics. The X on each combobox (and the
 * shared «Сбросить все») clears that filter back to «Все».
 */
export function SuppliersFilterBar({
  search,
  country,
  assignee,
  brand,
  status,
  options,
}: SuppliersFilterBarProps) {
  const { navigate } = useFilterNavigation();

  const countryOptions = useMemo<FilterOption[]>(
    () => options.countries.map((c) => ({ id: c, label: c })),
    [options.countries]
  );
  const assigneeOptions = useMemo<FilterOption[]>(
    () =>
      options.assignees.map((a) => ({ id: a.id, label: a.full_name })),
    [options.assignees]
  );
  const brandOptions = useMemo<FilterOption[]>(
    () => options.brands.map((b) => ({ id: b, label: b })),
    [options.brands]
  );

  const hasActiveFilters =
    Boolean(search) ||
    Boolean(country) ||
    Boolean(assignee) ||
    Boolean(brand) ||
    (status !== "" && status !== "all");

  function clearAll() {
    navigate({
      q: undefined,
      country: undefined,
      assignee: undefined,
      brand: undefined,
      status: undefined,
    });
  }

  const getLabel = (item: FilterOption) => item.label;

  return (
    <FilterBar hasActiveFilters={hasActiveFilters} onClearAll={clearAll}>
      <SearchInputFilter
        value={search || null}
        onChange={(next) => navigate({ q: next ?? undefined })}
        placeholder="Поиск по названию / коду…"
        ariaLabel="Поиск поставщика"
      />
      <SearchableCombobox<FilterOption>
        value={country || null}
        onChange={(id) => navigate({ country: id ?? undefined })}
        items={countryOptions}
        getLabel={getLabel}
        placeholder="Страна"
        searchPlaceholder="Поиск страны..."
        emptyMessage="Нет стран"
        ariaLabel="Фильтр: Страна"
        className="w-44"
      />
      <SearchableCombobox<FilterOption>
        value={assignee || null}
        onChange={(id) => navigate({ assignee: id ?? undefined })}
        items={assigneeOptions}
        getLabel={getLabel}
        placeholder="МОЗ"
        searchPlaceholder="Поиск МОЗ..."
        emptyMessage="Нет МОЗ"
        ariaLabel="Фильтр: МОЗ"
        className="w-44"
      />
      <SearchableCombobox<FilterOption>
        value={brand || null}
        onChange={(id) => navigate({ brand: id ?? undefined })}
        items={brandOptions}
        getLabel={getLabel}
        placeholder="Бренд"
        searchPlaceholder="Поиск бренда..."
        emptyMessage="Нет брендов"
        ariaLabel="Фильтр: Бренд"
        className="w-44"
      />
      <SearchableCombobox<FilterOption>
        value={status && status !== "all" ? status : null}
        onChange={(id) => navigate({ status: id ?? undefined })}
        items={STATUS_OPTIONS as readonly FilterOption[]}
        getLabel={getLabel}
        placeholder="Статус"
        searchPlaceholder="Поиск статуса..."
        emptyMessage="Нет статусов"
        ariaLabel="Фильтр: Статус"
        className="w-40"
      />
    </FilterBar>
  );
}
