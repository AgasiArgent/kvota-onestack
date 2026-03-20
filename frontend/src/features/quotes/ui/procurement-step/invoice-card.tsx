"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Paperclip } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";

// Columns from migration 188 (may not exist in DB types yet)
type ItemExtras = {
  dimension_height_mm?: number | null;
  dimension_width_mm?: number | null;
  dimension_length_mm?: number | null;
  vat_rate?: number | null;
  supplier_sku_note?: string | null;
};

type InvoiceExtras = {
  invoice_file_url?: string | null;
};

/** Safe accessor for columns that may be added by future migrations */
function ext<T>(row: unknown): T {
  return row as T;
}

const numberFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const qtyFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

interface InvoiceCardProps {
  invoice: QuoteInvoiceRow;
  items: QuoteItemRow[];
  defaultExpanded?: boolean;
}

export function InvoiceCard({
  invoice,
  items,
  defaultExpanded = false,
}: InvoiceCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const supplierName =
    (invoice.supplier as { name: string } | null)?.name ?? "\u2014";
  const totalAmount = items.reduce((sum, item) => {
    const price = item.purchase_price_original ?? 0;
    return sum + price * item.quantity;
  }, 0);
  const currency = invoice.currency ?? "USD";
  const hasFile = ext<InvoiceExtras>(invoice).invoice_file_url != null;

  return (
    <Card className="overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-muted/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={16} className="shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight size={16} className="shrink-0 text-muted-foreground" />
        )}

        <span className="font-medium text-sm truncate">
          {invoice.invoice_number}
        </span>

        <span className="text-sm text-muted-foreground truncate">
          {supplierName}
        </span>

        <Badge variant="secondary" className="ml-auto shrink-0">
          {items.length} поз.
        </Badge>

        <span className="text-sm font-mono tabular-nums shrink-0">
          {numberFmt.format(totalAmount)} {currency}
        </span>

        {invoice.status && (
          <Badge variant="outline" className="shrink-0">
            {invoice.status}
          </Badge>
        )}

        {hasFile && (
          <Paperclip size={14} className="shrink-0 text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-border overflow-x-auto">
          <ProcurementTable items={items} invoiceNumber={invoice.invoice_number} />
        </div>
      )}
    </Card>
  );
}

function ProcurementTable({
  items,
  invoiceNumber,
}: {
  items: QuoteItemRow[];
  invoiceNumber: string;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-28">Бренд</TableHead>
          <TableHead className="w-28">Арт.(запрос)</TableHead>
          <TableHead className="w-28">Арт.(произв.)</TableHead>
          <TableHead>Наименование</TableHead>
          <TableHead className="w-16 text-right">Кол-во</TableHead>
          <TableHead className="w-24 text-right">Цена</TableHead>
          <TableHead className="w-16">Валюта</TableHead>
          <TableHead className="w-24">Готовность</TableHead>
          <TableHead className="w-20 text-right">Вес, кг</TableHead>
          <TableHead className="w-28">Габариты, мм</TableHead>
          <TableHead className="w-16 text-right">НДС %</TableHead>
          <TableHead className="w-24">Инвойс</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => {
          const extras = ext<ItemExtras>(item);
          const hasMismatch =
            item.supplier_sku != null &&
            item.idn_sku != null &&
            item.supplier_sku !== item.idn_sku;

          const dimensions = formatDimensions(
            extras.dimension_height_mm,
            extras.dimension_width_mm,
            extras.dimension_length_mm
          );

          const readiness = formatReadiness(item.production_time_days);
          const vatRate = extras.vat_rate;
          const skuNote = extras.supplier_sku_note;

          return (
            <MismatchRow
              key={item.id}
              item={item}
              hasMismatch={hasMismatch}
              dimensions={dimensions}
              readiness={readiness}
              vatRate={vatRate}
              skuNote={skuNote}
              invoiceNumber={invoiceNumber}
            />
          );
        })}

        {items.length === 0 && (
          <TableRow>
            <TableCell colSpan={12} className="text-center py-6 text-muted-foreground">
              Нет позиций в этом инвойсе
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}

function MismatchRow({
  item,
  hasMismatch,
  dimensions,
  readiness,
  vatRate,
  skuNote,
  invoiceNumber,
}: {
  item: QuoteItemRow;
  hasMismatch: boolean;
  dimensions: string;
  readiness: string;
  vatRate: number | null | undefined;
  skuNote: string | null | undefined;
  invoiceNumber: string;
}) {
  return (
    <>
      <TableRow
        className={cn(hasMismatch && "bg-amber-50 border-l-4 border-l-amber-400")}
      >
        <TableCell className="truncate max-w-28">
          {item.brand ?? "\u2014"}
        </TableCell>
        <TableCell className="truncate max-w-28 font-mono text-xs">
          {item.idn_sku ?? "\u2014"}
        </TableCell>
        <TableCell className="truncate max-w-28 font-mono text-xs">
          {item.supplier_sku ?? "\u2014"}
        </TableCell>
        <TableCell className="truncate max-w-48">
          {item.product_name}
        </TableCell>
        <TableCell className="text-right font-mono">
          {qtyFmt.format(item.quantity)}
        </TableCell>
        <TableCell className="text-right font-mono">
          {item.purchase_price_original != null
            ? numberFmt.format(item.purchase_price_original)
            : "\u2014"}
        </TableCell>
        <TableCell className="text-xs">
          {item.purchase_currency ?? "\u2014"}
        </TableCell>
        <TableCell>{readiness}</TableCell>
        <TableCell className="text-right font-mono">
          {item.weight_in_kg != null
            ? numberFmt.format(item.weight_in_kg)
            : "\u2014"}
        </TableCell>
        <TableCell className="text-xs font-mono">{dimensions}</TableCell>
        <TableCell className="text-right font-mono">
          {vatRate != null ? `${vatRate}%` : "\u2014"}
        </TableCell>
        <TableCell className="text-xs text-muted-foreground">
          {invoiceNumber}
        </TableCell>
      </TableRow>

      {hasMismatch && skuNote && (
        <TableRow className="bg-amber-50/60">
          <TableCell colSpan={12} className="py-1.5 px-4 text-xs text-amber-800">
            <span className="font-medium">Примечание:</span>{" "}
            {skuNote}
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function formatDimensions(
  height: number | null | undefined,
  width: number | null | undefined,
  length: number | null | undefined
): string {
  if (height == null && width == null && length == null) return "\u2014";
  return `${height ?? 0}\u00D7${width ?? 0}\u00D7${length ?? 0}`;
}

function formatReadiness(productionTimeDays: number | null | undefined): string {
  if (productionTimeDays == null || productionTimeDays === 0) {
    return "\u2713 Готов";
  }
  return `\u25F7 ${productionTimeDays} дн.`;
}
