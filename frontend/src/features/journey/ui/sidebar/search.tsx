"use client";

/**
 * Search input (Req 3.5). Matches across route / title / proposed_route /
 * node_id; the filter engine (`applyJourneyFilters`) fades non-matches.
 */

import { Search as SearchIcon } from "lucide-react";
import { Input } from "@/components/ui/input";

interface Props {
  readonly value: string;
  readonly onChange: (next: string) => void;
}

export function JourneySearch({ value, onChange }: Props) {
  return (
    <div
      className="relative flex items-center"
      data-testid="journey-search"
    >
      <SearchIcon
        aria-hidden
        className="pointer-events-none absolute left-2 h-4 w-4 text-text-subtle"
      />
      <Input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Поиск по узлам"
        aria-label="Поиск"
        className="pl-7"
      />
    </div>
  );
}
