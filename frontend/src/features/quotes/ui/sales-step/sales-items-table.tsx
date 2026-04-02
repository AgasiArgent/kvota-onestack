import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { QuoteItemRow } from "@/entities/quote/queries";

const CURRENCY_SYMBOLS: Record<string, string> = {
  EUR: "\u20AC",
  USD: "$",
  CNY: "\u00A5",
  RUB: "\u20BD",
};

const numberFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const qtyFmt = new Intl.NumberFormat("ru-RU", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

interface SalesItemsTableProps {
  items: QuoteItemRow[];
  currency: string;
  quoteId?: string;
}

export function SalesItemsTable({ items, currency, quoteId }: SalesItemsTableProps) {
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;

  const totalQty = items.reduce((sum, item) => sum + item.quantity, 0);
  const totalAmount = items.reduce((sum, item) => {
    const price = item.base_price_vat ?? 0;
    return sum + price * item.quantity;
  }, 0);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-10 text-center">#</TableHead>
          <TableHead className="w-28">Бренд</TableHead>
          <TableHead className="w-40">Артикул</TableHead>
          <TableHead>Наименование</TableHead>
          <TableHead className="w-20 text-right">Кол-во</TableHead>
          <TableHead className="w-28 text-right">
            Цена ({symbol})
          </TableHead>
          <TableHead className="w-32 text-right">
            Итого ({symbol})
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {/* Totals row */}
        <TableRow className="bg-accent-subtle font-semibold">
          <TableCell className="text-center text-muted-foreground">
            {"\u03A3"}
          </TableCell>
          <TableCell />
          <TableCell />
          <TableCell>ИТОГО:</TableCell>
          <TableCell className="text-right font-mono">
            {qtyFmt.format(totalQty)}
          </TableCell>
          <TableCell />
          <TableCell className="text-right font-mono">
            {numberFmt.format(totalAmount)}
          </TableCell>
        </TableRow>

        {/* Item rows */}
        {items.map((item, idx) => {
          const price = item.base_price_vat ?? 0;
          const lineTotal = price * item.quantity;
          return (
            <TableRow key={item.id}>
              <TableCell className="text-center text-muted-foreground">
                {idx + 1}
              </TableCell>
              <TableCell className="truncate max-w-28">
                {item.brand ?? "\u2014"}
              </TableCell>
              <TableCell className="truncate max-w-40 font-mono text-xs">
                {item.product_code ?? "\u2014"}
              </TableCell>
              <TableCell>{item.product_name}</TableCell>
              <TableCell className="text-right font-mono">
                {qtyFmt.format(item.quantity)}
              </TableCell>
              <TableCell className="text-right font-mono">
                {item.base_price_vat != null
                  ? numberFmt.format(item.base_price_vat)
                  : "\u2014"}
              </TableCell>
              <TableCell className="text-right font-mono">
                {numberFmt.format(lineTotal)}
              </TableCell>
            </TableRow>
          );
        })}

        {items.length === 0 && (
          <TableRow>
            <TableCell colSpan={7} className="text-center py-8">
              <p className="text-muted-foreground">Нет позиций</p>
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
