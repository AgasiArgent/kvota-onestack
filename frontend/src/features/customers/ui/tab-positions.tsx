import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { ScrollableTable } from "@/shared/ui/scrollable-table";

interface Position {
  id: string;
  product_name: string;
  brand: string | null;
  sku: string | null;
  idn_sku: string | null;
  quantity: number | null;
  purchase_price: number | null;
  purchase_currency: string | null;
  procurement_date: string | null;
  quote_idn: string;
}

interface Props {
  positions: Position[];
}

function formatPrice(price: number | null, currency: string | null) {
  if (price == null) return "—";
  const symbol = currency === "RUB" ? "₽" : currency === "EUR" ? "€" : "$";
  return `${price.toLocaleString("ru-RU")} ${symbol}`;
}

function formatDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function TabPositions({ positions }: Props) {
  if (positions.length === 0) {
    return <p className="py-8 text-center text-text-subtle">Нет запрошенных позиций</p>;
  }
  return (
    <ScrollableTable>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Наименование</TableHead>
            <TableHead>Бренд</TableHead>
            <TableHead>Артикул</TableHead>
            <TableHead>IDN-SKU</TableHead>
            <TableHead className="text-right">Кол-во</TableHead>
            <TableHead className="text-right">Цена закупки</TableHead>
            <TableHead>Дата закупки</TableHead>
            <TableHead>КП</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {positions.map((p) => (
            <TableRow key={p.id}>
              <TableCell className="font-medium">{p.product_name}</TableCell>
              <TableCell className="text-text-muted">{p.brand ?? "—"}</TableCell>
              <TableCell className="text-text-muted">{p.sku ?? "—"}</TableCell>
              <TableCell className="text-text-muted">{p.idn_sku ?? "—"}</TableCell>
              <TableCell className="text-right tabular-nums">{p.quantity ?? "—"}</TableCell>
              <TableCell className="text-right tabular-nums">
                {formatPrice(p.purchase_price, p.purchase_currency)}
              </TableCell>
              <TableCell className="text-text-muted tabular-nums">
                {formatDate(p.procurement_date)}
              </TableCell>
              <TableCell className="text-text-muted">{p.quote_idn}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </ScrollableTable>
  );
}
