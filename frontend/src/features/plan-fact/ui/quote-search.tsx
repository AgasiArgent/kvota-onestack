"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { useDebounce } from "@/shared/lib/use-debounce";
import { searchQuotes } from "@/features/plan-fact/api";
import type { QuoteSearchResult } from "@/entities/finance";

interface QuoteSearchProps {
  onSelect: (result: QuoteSearchResult) => void;
}

const MIN_QUERY_LENGTH = 3;
const DEBOUNCE_MS = 300;

export function QuoteSearch({ onSelect }: QuoteSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<QuoteSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const debouncedQuery = useDebounce(query, DEBOUNCE_MS);

  useEffect(() => {
    if (debouncedQuery.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setIsOpen(false);
      setError(null);
      return;
    }

    let cancelled = false;

    async function doSearch() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await searchQuotes(debouncedQuery);
        if (!cancelled) {
          setResults(data);
          setIsOpen(true);
        }
      } catch {
        if (!cancelled) {
          setError("Ошибка поиска");
          setResults([]);
          setIsOpen(true);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    doSearch();

    return () => {
      cancelled = true;
    };
  }, [debouncedQuery]);

  const handleSelect = useCallback(
    (result: QuoteSearchResult) => {
      setQuery(result.idn);
      setIsOpen(false);
      onSelect(result);
    },
    [onSelect],
  );

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <Input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Поиск по номеру КП..."
        className="w-full"
      />

      {query.length > 0 && query.length < MIN_QUERY_LENGTH && (
        <p className="mt-1 text-xs text-muted-foreground">
          Введите минимум {MIN_QUERY_LENGTH} символа
        </p>
      )}

      {isLoading && (
        <p className="mt-1 text-xs text-muted-foreground">Поиск...</p>
      )}

      {isOpen && !isLoading && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md">
          {error ? (
            <div className="px-3 py-2 text-sm text-destructive">{error}</div>
          ) : results.length === 0 ? (
            <div className="px-3 py-2 text-sm text-muted-foreground">
              Не найдено
            </div>
          ) : (
            <ul className="max-h-60 overflow-auto py-1">
              {results.map((result) => (
                <li key={result.id}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-3 px-3 py-2 text-sm hover:bg-accent transition-colors text-left"
                    onClick={() => handleSelect(result)}
                  >
                    <span className="font-medium">{result.idn}</span>
                    <span className="text-muted-foreground truncate">
                      {result.customer_name}
                    </span>
                    <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                      {result.deal_number}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
