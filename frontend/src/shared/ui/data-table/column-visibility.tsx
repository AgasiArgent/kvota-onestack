"use client";

import { Columns3 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";

import type { DataTableColumn } from "./types";

interface ColumnVisibilityProps<T> {
  columns: readonly DataTableColumn<T>[];
  visibleKeys: readonly string[];
  onChange: (keys: readonly string[]) => void;
}

/**
 * Popover that lets the user show/hide columns.
 *
 * Columns marked `alwaysVisible` are excluded from the list and remain visible.
 * Toggles are applied immediately (no apply button) and propagated via `onChange`.
 * Stale keys (columns removed from the config) are silently ignored during toggle.
 */
export function ColumnVisibility<T>({
  columns,
  visibleKeys,
  onChange,
}: ColumnVisibilityProps<T>) {
  const toggleableColumns = columns.filter((c) => !c.alwaysVisible);
  const visibleSet = new Set(visibleKeys);

  function toggle(key: string, checked: boolean) {
    const next = new Set(visibleKeys);
    if (checked) next.add(key);
    else next.delete(key);
    // Reconcile: drop any keys not in the current config.
    const known = new Set(columns.map((c) => c.key));
    const reconciled = Array.from(next).filter((k) => known.has(k));
    onChange(reconciled);
  }

  function handleShowAll() {
    const known = new Set(columns.map((c) => c.key));
    onChange(Array.from(known));
  }

  function handleReset() {
    // Reset to defaults: columns with defaultVisible !== false
    const defaults = columns.filter((c) => c.defaultVisible !== false).map((c) => c.key);
    onChange(defaults);
  }

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            aria-label="Настроить колонки"
          >
            <Columns3 size={14} />
            Колонки
          </Button>
        }
      />
      <PopoverContent className="w-56 p-0" side="bottom" align="end">
        <div className="flex flex-col">
          <div className="border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground">
            Видимые колонки
          </div>
          <div className="max-h-64 overflow-y-auto py-1">
            {toggleableColumns.length === 0 ? (
              <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                Нет колонок для настройки
              </div>
            ) : (
              toggleableColumns.map((column) => (
                <label
                  key={column.key}
                  className="flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-muted/50 cursor-pointer"
                >
                  <Checkbox
                    checked={visibleSet.has(column.key)}
                    onCheckedChange={(checked) =>
                      toggle(column.key, checked === true)
                    }
                  />
                  <span className="truncate">{column.label}</span>
                </label>
              ))
            )}
          </div>
          <div className="flex gap-2 border-t border-border p-2">
            <Button
              variant="ghost"
              size="xs"
              className="flex-1"
              onClick={handleReset}
            >
              По умолчанию
            </Button>
            <Button
              variant="ghost"
              size="xs"
              className="flex-1"
              onClick={handleShowAll}
            >
              Показать все
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
