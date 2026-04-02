"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { QuoteItemRow, QuoteInvoiceRow } from "@/entities/quote/queries";

/** Safe accessor for columns that may be added by future migrations */
function ext<T>(row: unknown): T {
  return row as T;
}

type ItemExtras = {
  dimension_height_mm?: number | null;
  dimension_width_mm?: number | null;
  dimension_length_mm?: number | null;
};

const numberFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const qtyFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

interface ProductsSubtableProps {
  items: QuoteItemRow[];
  invoice: QuoteInvoiceRow;
}

export function ProductsSubtable({ items, invoice }: ProductsSubtableProps) {
  return (
    <div>
      <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wide px-4 py-2 border-b border-border bg-muted/30">
        Товары
      </h4>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Товар</TableHead>
            <TableHead className="w-36">Артикул</TableHead>
            <TableHead className="w-20 text-right">Кол-во</TableHead>
            <TableHead className="w-24 text-right">Вес, кг</TableHead>
            <TableHead className="w-36">Габариты, мм</TableHead>
            <TableHead className="w-20 text-right">Мест</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => {
            const extras = ext<ItemExtras>(item);
            const dimensions = formatDimensions(
              extras.dimension_height_mm,
              extras.dimension_width_mm,
              extras.dimension_length_mm
            );

            return (
              <TableRow key={item.id}>
                <TableCell className="truncate max-w-48">
                  {item.product_name}
                </TableCell>
                <TableCell className="text-xs font-mono truncate max-w-36">
                  {item.product_code ?? "\u2014"}
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {qtyFmt.format(item.quantity)}
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {item.weight_in_kg != null
                    ? numberFmt.format(item.weight_in_kg)
                    : "\u2014"}
                </TableCell>
                <TableCell className="text-xs font-mono">
                  {dimensions}
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {invoice.package_count ?? "\u2014"}
                </TableCell>
              </TableRow>
            );
          })}

          {items.length === 0 && (
            <TableRow>
              <TableCell
                colSpan={5}
                className="text-center py-4 text-muted-foreground"
              >
                Нет позиций
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
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
