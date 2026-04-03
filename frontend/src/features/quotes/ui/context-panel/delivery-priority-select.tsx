"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { patchQuote } from "@/entities/quote/mutations";

const PRIORITY_OPTIONS = [
  { value: "fast", label: "Быстрее" },
  { value: "cheap", label: "Дешевле" },
  { value: "normal", label: "Обычно" },
] as const;

const PRIORITY_LABELS: Record<string, string> = Object.fromEntries(
  PRIORITY_OPTIONS.map((o) => [o.value, o.label])
);

interface DeliveryPrioritySelectProps {
  quoteId: string;
  initialValue: string | null;
}

export function DeliveryPrioritySelect({
  quoteId,
  initialValue,
}: DeliveryPrioritySelectProps) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(initialValue);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleSelect(value: string) {
    const prev = selected;
    setSelected(value);
    setOpen(false);

    try {
      await patchQuote(quoteId, { delivery_priority: value });
    } catch {
      setSelected(prev);
      toast.error("Не удалось сохранить");
    }
  }

  async function handleClear(e: React.MouseEvent) {
    e.stopPropagation();
    const prev = selected;
    setSelected(null);

    try {
      await patchQuote(quoteId, { delivery_priority: null });
    } catch {
      setSelected(prev);
      toast.error("Не удалось сохранить");
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-sm font-medium hover:text-accent transition-colors"
      >
        <span>{selected ? PRIORITY_LABELS[selected] ?? selected : "\u2014"}</span>
        {selected ? (
          <X
            size={12}
            className="shrink-0 text-muted-foreground hover:text-foreground"
            onClick={handleClear}
          />
        ) : (
          <ChevronDown size={12} className="shrink-0 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="absolute top-full right-0 z-[300] mt-1 min-w-[140px] rounded-lg border bg-popover shadow-md p-1">
          {PRIORITY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => handleSelect(opt.value)}
              className={cn(
                "flex w-full items-center rounded-md px-2 py-1.5 text-sm cursor-default",
                "hover:bg-accent hover:text-accent-foreground",
                opt.value === selected && "bg-accent/10 font-medium"
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
