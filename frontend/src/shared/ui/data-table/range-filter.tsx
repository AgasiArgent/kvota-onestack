"use client";

import { useEffect, useState } from "react";
import { Filter } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

interface RangeFilterProps {
  columnKey: string;
  title: string;
  unit?: string;
  value?: { min?: number; max?: number };
  onApply: (value: { min?: number; max?: number }) => void;
  onReset: () => void;
}

/**
 * Numeric range filter popover.
 *
 * Two numeric inputs (min/max) with optional unit label. Either bound may be
 * undefined (open-ended). Apply with both empty = reset.
 */
export function RangeFilter({
  title,
  unit,
  value,
  onApply,
  onReset,
}: RangeFilterProps) {
  const [open, setOpen] = useState(false);
  const [minInput, setMinInput] = useState("");
  const [maxInput, setMaxInput] = useState("");

  // Sync local input state when popover opens.
  useEffect(() => {
    if (open) {
      setMinInput(value?.min !== undefined ? String(value.min) : "");
      setMaxInput(value?.max !== undefined ? String(value.max) : "");
    }
  }, [open, value]);

  function parseNumeric(input: string): number | undefined {
    const trimmed = input.trim();
    if (trimmed.length === 0) return undefined;
    const n = Number(trimmed);
    return Number.isFinite(n) ? n : undefined;
  }

  function handleApply() {
    const min = parseNumeric(minInput);
    const max = parseNumeric(maxInput);
    if (min === undefined && max === undefined) {
      onReset();
    } else {
      onApply({ min, max });
    }
    setOpen(false);
  }

  function handleReset() {
    setMinInput("");
    setMaxInput("");
    onReset();
    setOpen(false);
  }

  const isActive = value?.min !== undefined || value?.max !== undefined;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <button
            type="button"
            aria-label={`Фильтр диапазона: ${title}`}
            className={cn(
              "inline-flex items-center justify-center rounded p-0.5 transition-colors",
              isActive
                ? "text-accent hover:text-accent-hover"
                : "text-muted-foreground/60 hover:text-foreground"
            )}
            onClick={(e) => e.stopPropagation()}
          >
            <Filter size={12} />
            {isActive && (
              <span className="ml-0.5 size-1.5 rounded-full bg-accent" />
            )}
          </button>
        }
      />
      <PopoverContent className="w-56 p-0" side="bottom" align="start">
        <div className="flex flex-col">
          <div className="border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground">
            {title}
          </div>
          <div className="space-y-2 p-3">
            <div className="flex flex-col gap-1">
              <Label className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                От {unit ? `(${unit})` : ""}
              </Label>
              <Input
                type="number"
                inputMode="decimal"
                value={minInput}
                onChange={(e) => setMinInput(e.target.value)}
                placeholder="Мин."
                className="h-7 text-xs tabular-nums"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleApply();
                }}
                autoFocus
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">
                До {unit ? `(${unit})` : ""}
              </Label>
              <Input
                type="number"
                inputMode="decimal"
                value={maxInput}
                onChange={(e) => setMaxInput(e.target.value)}
                placeholder="Макс."
                className="h-7 text-xs tabular-nums"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleApply();
                }}
              />
            </div>
          </div>
          <div className="flex gap-2 border-t border-border p-2">
            <Button
              variant="ghost"
              size="xs"
              className="flex-1"
              onClick={handleReset}
              disabled={!isActive && minInput === "" && maxInput === ""}
            >
              Сбросить
            </Button>
            <Button
              variant="default"
              size="xs"
              className="flex-1"
              onClick={handleApply}
            >
              Применить
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
