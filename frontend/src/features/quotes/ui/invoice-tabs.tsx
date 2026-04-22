"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

/**
 * InvoiceTabs — per-invoice selector shared between logistics-step and
 * customs-step on quote detail. A quote can have multiple invoices
 * ("2 КП от разных поставщиков" per spec §3.1); each invoice is priced
 * independently for logistics & customs, so the UI needs a scope switcher.
 *
 * Trigger shows a small status dot (pending/in_progress/completed)
 * drawn from semantic DS tokens. Dot diameter is the one `rounded-full`
 * exception allowed by design-system.md.
 */

export type InvoiceTabStatus = "pending" | "in_progress" | "completed";

export interface InvoiceTabItem {
  id: string;
  /** Visible label, e.g. "Инвойс #1 · Shanghai Ind". */
  displayName: string;
  /** Secondary metadata, e.g. "12 поз · 840 кг". */
  subLabel?: string;
  status: InvoiceTabStatus;
}

interface InvoiceTabsProps {
  invoices: InvoiceTabItem[];
  activeInvoiceId: string;
  onInvoiceChange: (id: string) => void;
  className?: string;
}

const STATUS_DOT: Record<InvoiceTabStatus, { cls: string; label: string }> = {
  pending: { cls: "bg-text-subtle", label: "Ожидает" },
  in_progress: { cls: "bg-warning", label: "В работе" },
  completed: { cls: "bg-success", label: "Завершено" },
};

export function InvoiceTabs({
  invoices,
  activeInvoiceId,
  onInvoiceChange,
  className,
}: InvoiceTabsProps) {
  if (invoices.length === 0) return null;

  return (
    <Tabs
      value={activeInvoiceId}
      onValueChange={onInvoiceChange}
      className={className}
    >
      <TabsList
        className={cn(
          "h-auto w-full justify-start gap-1 overflow-x-auto p-1",
          "bg-sidebar border border-border-light rounded-md",
        )}
      >
        {invoices.map((inv) => {
          const dot = STATUS_DOT[inv.status];
          return (
            <TabsTrigger
              key={inv.id}
              value={inv.id}
              className={cn(
                "h-auto flex-col items-start gap-1 px-3 py-2",
                "text-left whitespace-nowrap",
                "data-[state=active]:bg-card data-[state=active]:shadow-sm",
              )}
            >
              <div className="flex items-center gap-2 text-sm font-medium">
                <span
                  className={cn("size-1.5 rounded-full", dot.cls)}
                  aria-label={dot.label}
                  role="img"
                />
                <span>{inv.displayName}</span>
              </div>
              {inv.subLabel && (
                <span className="text-xs text-text-muted tabular-nums">
                  {inv.subLabel}
                </span>
              )}
            </TabsTrigger>
          );
        })}
      </TabsList>
    </Tabs>
  );
}
