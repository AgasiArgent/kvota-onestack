"use client";

import { Package } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SupplierQuoteItem } from "@/entities/supplier/types";

interface Props {
  items: SupplierQuoteItem[];
}

function formatPrice(price: number | null, currency: string | null): string {
  if (price == null) return "—";
  const formatted = price.toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return currency ? `${formatted} ${currency}` : formatted;
}

export function TabPositions({ items }: Props) {
  if (items.length === 0) {
    return (
      <div className="py-12 text-center">
        <Package size={40} className="mx-auto text-text-subtle mb-3" />
        <p className="text-text-muted mb-1">Нет позиций</p>
        <p className="text-xs text-text-subtle">
          Позиции появятся после добавления поставщика в котировки
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Наименование</TableHead>
            <TableHead>Бренд</TableHead>
            <TableHead>Артикул</TableHead>
            <TableHead className="text-right">Кол-во</TableHead>
            <TableHead className="text-right">Закуп. цена</TableHead>
            <TableHead>Котировка</TableHead>
            <TableHead>Дата закупки</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id}>
              <TableCell className="font-medium max-w-[250px] truncate">
                {item.product_name ?? "—"}
              </TableCell>
              <TableCell>{item.brand ?? "—"}</TableCell>
              <TableCell className="text-text-muted">
                {item.sku ?? item.idn_sku ?? "—"}
              </TableCell>
              <TableCell className="text-right">{item.quantity ?? "—"}</TableCell>
              <TableCell className="text-right">
                {formatPrice(item.purchase_price, item.purchase_currency)}
              </TableCell>
              <TableCell className="text-text-muted">{item.quote_idn}</TableCell>
              <TableCell className="text-text-muted">
                {item.procurement_date
                  ? new Date(item.procurement_date).toLocaleDateString("ru-RU")
                  : "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
