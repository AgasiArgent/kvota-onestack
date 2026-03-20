"use client";

import { useState, useMemo } from "react";
import { Plus, ArrowRight, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
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
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";

const qtyFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

interface UnassignedItemsProps {
  items: QuoteItemRow[];
  invoices: QuoteInvoiceRow[];
}

export function UnassignedItems({ items, invoices }: UnassignedItemsProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const unassigned = useMemo(
    () => items.filter((i) => i.invoice_id == null),
    [items]
  );

  if (unassigned.length === 0) return null;

  const allSelected =
    unassigned.length > 0 && selectedIds.size === unassigned.length;

  function toggleAll() {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(unassigned.map((i) => i.id)));
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
    console.log(
      "Create invoice with items:",
      Array.from(selectedIds)
    );
  }

  function handleAssignToInvoice(invoiceId: string) {
    console.log(
      "Assign items to invoice:",
      invoiceId,
      Array.from(selectedIds)
    );
  }

  const hasSelection = selectedIds.size > 0;

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50/50">
      <div className="px-4 py-3 flex items-center justify-between border-b border-amber-200">
        <h3 className="text-sm font-semibold text-amber-900">
          Нераспределённые позиции ({unassigned.length})
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
            <TableHead className="w-32">Артикул</TableHead>
            <TableHead>Наименование</TableHead>
            <TableHead className="w-20 text-right">Кол-во</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {unassigned.map((item) => (
            <TableRow
              key={item.id}
              className={cn(
                selectedIds.has(item.id) && "bg-amber-100/60"
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
              <TableCell className="truncate max-w-32 font-mono text-xs">
                {item.idn_sku ?? "\u2014"}
              </TableCell>
              <TableCell>{item.product_name}</TableCell>
              <TableCell className="text-right font-mono">
                {qtyFmt.format(item.quantity)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {hasSelection && (
        <div className="px-4 py-3 border-t border-amber-200 flex items-center gap-2 bg-amber-100/40">
          <span className="text-sm text-amber-900 mr-2">
            Выбрано: {selectedIds.size}
          </span>
          <Button
            size="sm"
            className="bg-accent text-white hover:bg-accent-hover"
            onClick={handleCreateWithSelected}
          >
            <Plus size={14} />
            Создать инвойс с выбранными
          </Button>

          {invoices.length > 0 && (
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button size="sm" variant="outline">
                    <ArrowRight size={14} />
                    Назначить в инвойс
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
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      )}
    </div>
  );
}
