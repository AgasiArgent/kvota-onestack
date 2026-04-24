"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Plus, ArrowRight, ChevronDown, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { createClient } from "@/shared/lib/supabase/client";
import { extractErrorMessage } from "@/shared/lib/errors";
import { assignItemsToInvoice } from "@/entities/quote/mutations";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";

const qtyFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

/**
 * Map: quote_item_id → list of invoices currently covering it via
 * invoice_item_coverage → invoice_items → invoices. The component accepts
 * this map as a prop for testability; when omitted, the component fetches
 * it on mount from Supabase.
 */
export interface CoverageChip {
  invoice_id: string;
  invoice_number: string;
}

interface QuotePositionsListProps {
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
  onCreateInvoiceWithItems?: (itemIds: string[]) => void;
  /**
   * Optional coverage override for tests / SSR. When omitted, component
   * fetches via useEffect on mount.
   */
  coverageByQuoteItem?: Record<string, CoverageChip[]>;
}

export function QuotePositionsList({
  items,
  invoices,
  onCreateInvoiceWithItems,
  coverageByQuoteItem: coverageOverride,
}: QuotePositionsListProps) {
  const router = useRouter();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [assigning, setAssigning] = useState(false);
  const [fetchedCoverage, setFetchedCoverage] = useState<
    Record<string, CoverageChip[]>
  >({});

  const coverageByQuoteItem = coverageOverride ?? fetchedCoverage;
  const hasCoverageOverride = coverageOverride !== undefined;

  const loadCoverage = useCallback(async () => {
    if (items.length === 0) {
      setFetchedCoverage({});
      return;
    }

    const supabase = createClient();

    const { data, error } = await supabase
      .from("invoice_item_coverage")
      .select("quote_item_id, invoice_items!inner(invoice_id, invoices!inner(id, invoice_number))")
      .in(
        "quote_item_id",
        items.map((i) => i.id)
      );

    if (error || !data) {
      setFetchedCoverage({});
      return;
    }

    const map: Record<string, CoverageChip[]> = {};
    for (const row of data as unknown as Array<{
      quote_item_id: string;
      invoice_items: {
        invoice_id: string;
        invoices: { id: string; invoice_number: string };
      };
    }>) {
      const qiId = row.quote_item_id;
      const inv = row.invoice_items?.invoices;
      if (!inv) continue;
      const list = map[qiId] ?? [];
      if (!list.some((c) => c.invoice_id === inv.id)) {
        list.push({ invoice_id: inv.id, invoice_number: inv.invoice_number });
      }
      map[qiId] = list;
    }
    setFetchedCoverage(map);
  }, [items]);

  useEffect(() => {
    if (hasCoverageOverride) return;
    void loadCoverage();
  }, [hasCoverageOverride, loadCoverage]);

  if (items.length === 0) return null;

  const allSelected = items.length > 0 && selectedIds.size === items.length;

  function toggleAll() {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(items.map((i) => i.id)));
    }
  }

  function toggleItem(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function handleCreateWithSelected() {
    onCreateInvoiceWithItems?.(Array.from(selectedIds));
  }

  function scrollToInvoice(invoiceId: string) {
    if (typeof document === "undefined") return;
    const el = document.querySelector(`[data-invoice-id="${invoiceId}"]`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  async function handleAssignToInvoice(invoiceId: string) {
    setAssigning(true);
    try {
      await assignItemsToInvoice(Array.from(selectedIds), invoiceId);
      toast.success(`${selectedIds.size} поз. назначено в КП`);
      setSelectedIds(new Set());
      router.refresh();
    } catch (err) {
      console.error("[quote-positions-list] assign failed:", err);
      toast.error(extractErrorMessage(err) ?? "Не удалось назначить позиции");
    } finally {
      setAssigning(false);
    }
  }

  const hasSelection = selectedIds.size > 0;

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="px-4 py-3 flex items-center justify-between border-b border-border">
        <h3 className="text-sm font-semibold">
          Позиции заявки ({items.length})
        </h3>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <Checkbox
                checked={allSelected}
                onCheckedChange={toggleAll}
              />
            </TableHead>
            <TableHead className="w-28">Бренд</TableHead>
            <TableHead className="w-40">Артикул</TableHead>
            <TableHead>Наименование</TableHead>
            <TableHead className="w-48">В КП</TableHead>
            <TableHead className="w-20 text-right">Кол-во</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const chips = coverageByQuoteItem[item.id] ?? [];
            const isCovered = chips.length > 0;
            return (
              <TableRow
                key={item.id}
                className={cn(
                  selectedIds.has(item.id) && "bg-muted/60",
                  !isCovered && "opacity-95"
                )}
              >
                <TableCell>
                  <Checkbox
                    checked={selectedIds.has(item.id)}
                    onCheckedChange={() => toggleItem(item.id)}
                  />
                </TableCell>
                <TableCell className="truncate max-w-28">
                  {item.brand ?? "\u2014"}
                </TableCell>
                <TableCell className="truncate max-w-40 font-mono text-xs">
                  {item.product_code ?? "\u2014"}
                </TableCell>
                <TableCell>{item.product_name}</TableCell>
                <TableCell>
                  {chips.length === 0 ? (
                    <span className="text-muted-foreground text-xs">
                      {"\u2014"}
                    </span>
                  ) : (
                    <div className="flex flex-wrap gap-1">
                      {chips.map((chip) => (
                        <button
                          key={chip.invoice_id}
                          type="button"
                          onClick={() => scrollToInvoice(chip.invoice_id)}
                          className="inline-flex"
                        >
                          <Badge
                            variant="secondary"
                            className="text-xs cursor-pointer hover:bg-secondary/80"
                          >
                            {chip.invoice_number}
                          </Badge>
                        </button>
                      ))}
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-right font-mono">
                  {qtyFmt.format(item.quantity)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>

      {hasSelection && (
        <div className="px-4 py-3 border-t border-border flex items-center gap-2 bg-muted/40">
          <span className="text-sm mr-2">
            Выбрано: {selectedIds.size}
          </span>

          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button size="sm" disabled={assigning}>
                  {assigning ? (
                    <Loader2 size={14} className="animate-spin" />
                  ) : (
                    <ArrowRight size={14} />
                  )}
                  Назначить в КП
                  <ChevronDown size={14} />
                </Button>
              }
            />
            <DropdownMenuContent align="start" sideOffset={4}>
              {invoices.map((inv) => (
                <DropdownMenuItem
                  key={inv.id}
                  onClick={() => handleAssignToInvoice(inv.id)}
                >
                  {inv.invoice_number}
                  {inv.supplier
                    ? ` \u2014 ${(inv.supplier as { name: string }).name}`
                    : ""}
                </DropdownMenuItem>
              ))}
              {invoices.length > 0 && <DropdownMenuSeparator />}
              <DropdownMenuItem onClick={handleCreateWithSelected}>
                <Plus size={14} />
                Создать новый КП
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
    </div>
  );
}
