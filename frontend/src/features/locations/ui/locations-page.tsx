"use client";

import { useState, useRef } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select";
import { LocationsTable } from "./locations-table";
import { useFilterNavigation } from "@/shared/lib/use-filter-navigation";
import type { LocationListItem, LocationStats } from "../model/types";

interface Props {
  locations: LocationListItem[];
  stats: LocationStats;
  countries: string[];
  initialSearch?: string;
  initialCountry?: string;
  initialStatus?: string;
}

const STATUS_OPTIONS = [
  { value: "all", label: "Все статусы" },
  { value: "active", label: "Активные" },
  { value: "inactive", label: "Неактивные" },
] as const;

export function LocationsPage({
  locations,
  stats,
  countries,
  initialSearch = "",
  initialCountry = "",
  initialStatus = "",
}: Props) {
  const getStatusLabel = (v: string) =>
    STATUS_OPTIONS.find((o) => o.value === v)?.label ?? "Все статусы";

  const [statusLabel, setStatusLabel] = useState(getStatusLabel(initialStatus || "all"));
  const [searchValue, setSearchValue] = useState(initialSearch);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const { navigate } = useFilterNavigation();

  const countryOptions = [
    { value: "all", label: "Все страны" },
    ...countries.map((c) => ({ value: c, label: c })),
  ];
  const getCountryLabel = (v: string) =>
    countryOptions.find((o) => o.value === v)?.label ?? "Все страны";
  const [countryLabel, setCountryLabel] = useState(
    getCountryLabel(initialCountry || "all")
  );

  function handleSearchChange(value: string) {
    setSearchValue(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      navigate({ q: value || undefined });
    }, 300);
  }

  function handleCountryChange(value: string | null) {
    const v = value ?? "all";
    setCountryLabel(getCountryLabel(v));
    navigate({ country: v });
  }

  function handleStatusChange(value: string | null) {
    const v = value ?? "all";
    setStatusLabel(getStatusLabel(v));
    navigate({ status: v });
  }

  return (
    <div className="space-y-4">
      {/* Search + Filter bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle" size={16} />
          <Input
            value={searchValue}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Поиск по коду, городу, стране..."
            className="pl-9"
          />
        </div>

        <Select
          defaultValue={initialCountry || "all"}
          onValueChange={handleCountryChange}
        >
          <SelectTrigger className="w-[160px]">
            <span className="flex flex-1 text-left">{countryLabel}</span>
          </SelectTrigger>
          <SelectContent>
            {countryOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

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
      </div>

      {/* Stats row */}
      <div className="flex gap-4 text-sm text-text-muted">
        <span>Всего: {stats.total}</span>
        <span>Активные: {stats.active}</span>
      </div>

      <LocationsTable locations={locations} />
    </div>
  );
}
