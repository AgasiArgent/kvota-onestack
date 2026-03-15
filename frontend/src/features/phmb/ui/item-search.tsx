"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import type { PriceListSearchResult } from "@/entities/phmb-quote/types";
import { searchPriceList } from "@/entities/phmb-quote/mutations";

interface ItemSearchProps {
  onAddItem: (item: PriceListSearchResult) => void;
  orgId: string;
}

export function ItemSearch({ onAddItem, orgId }: ItemSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PriceListSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const performSearch = useCallback(
    async (searchQuery: string) => {
      if (searchQuery.length < 2) {
        setResults([]);
        setIsOpen(false);
        return;
      }

      setIsLoading(true);
      try {
        const data = await searchPriceList(searchQuery, orgId);
        setResults(data);
        setIsOpen(data.length > 0);
      } catch {
        setResults([]);
        setIsOpen(false);
      } finally {
        setIsLoading(false);
      }
    },
    [orgId]
  );

  const handleInputChange = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => performSearch(value), 300);
    },
    [performSearch]
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelect(item: PriceListSearchResult) {
    onAddItem(item);
    // Keep search focused for rapid multi-item entry
    setIsOpen(false);
    inputRef.current?.focus();
  }

  function formatPrice(price: number | null) {
    if (!price) return "—";
    return new Intl.NumberFormat("ru-RU", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(price);
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Search
          className="absolute left-3 top-1/2 -translate-y-1/2 text-text-subtle"
          size={16}
        />
        <Input
          ref={inputRef}
          value={query}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => {
            if (results.length > 0) setIsOpen(true);
          }}
          placeholder="Поиск по артикулу или названию..."
          className="pl-9"
        />
        {isLoading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="h-4 w-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Dropdown */}
      {isOpen && results.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-card border border-border rounded-lg shadow-md max-h-80 overflow-y-auto">
          {results.map((item) => (
            <button
              key={item.id}
              type="button"
              className="w-full text-left px-4 py-3 hover:bg-accent-subtle transition-colors border-b border-border-light last:border-b-0"
              onClick={() => handleSelect(item)}
            >
              <div className="flex items-center justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-accent tabular-nums">
                      {item.cat_number}
                    </span>
                    {item.brand && (
                      <span className="text-xs text-text-muted bg-sidebar px-1.5 py-0.5 rounded-sm">
                        {item.brand}
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-text truncate mt-0.5">
                    {item.product_name}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-medium tabular-nums">
                    {formatPrice(item.list_price_rmb)} RMB
                  </div>
                  {item.discount_pct > 0 && (
                    <div className="text-xs text-text-muted">
                      скидка {item.discount_pct}%
                    </div>
                  )}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
