"use client";

import { useMemo, useState } from "react";
import { LayoutGrid, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import type { LogisticsTemplate } from "@/entities/logistics-template";
import { cn } from "@/lib/utils";

/**
 * TemplatePicker — dropdown to select and apply a pre-defined route
 * template to the active invoice. Applying a template materialises draft
 * segments on the server (see {@link applyLogisticsTemplate}).
 *
 * Includes a simple contains-filter for long lists; design-system.md
 * mandates searchable entity pickers once the list could realistically
 * grow beyond 6 items.
 */

interface TemplatePickerProps {
  templates: LogisticsTemplate[];
  onApply: (template: LogisticsTemplate) => void;
  disabled?: boolean;
  className?: string;
}

export function TemplatePicker({
  templates,
  onApply,
  disabled,
  className,
}: TemplatePickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return templates;
    return templates.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        (t.description ?? "").toLowerCase().includes(q),
    );
  }, [templates, query]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            className={cn("gap-2", className)}
          />
        }
      >
        <LayoutGrid size={14} strokeWidth={2} aria-hidden />
        Шаблон маршрута
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="border-b border-border-light p-2">
          <div className="relative">
            <Search
              size={14}
              strokeWidth={2}
              aria-hidden
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-text-subtle"
            />
            <Input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Поиск шаблона…"
              className="h-8 pl-8"
            />
          </div>
        </div>
        <div className="max-h-80 overflow-y-auto p-1">
          {filtered.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-text-subtle">
              {templates.length === 0
                ? "Шаблоны ещё не созданы"
                : "Ничего не найдено"}
            </div>
          ) : (
            filtered.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => {
                  onApply(template);
                  setOpen(false);
                  setQuery("");
                }}
                className={cn(
                  "flex w-full flex-col items-start gap-1 rounded-md px-3 py-2 text-left",
                  "hover:bg-sidebar focus:bg-sidebar focus:outline-none",
                )}
              >
                <span className="text-sm font-medium text-text">
                  {template.name}
                </span>
                <span className="text-xs text-text-muted">
                  {template.description ?? "—"}
                  <span className="mx-1.5 text-text-subtle">·</span>
                  {template.segments.length}{" "}
                  {template.segments.length === 1
                    ? "сегмент"
                    : "сегментов"}
                </span>
              </button>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
