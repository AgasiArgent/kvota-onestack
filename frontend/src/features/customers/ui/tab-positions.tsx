import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";

interface Position {
  id: string;
  product_name: string;
  brand: string | null;
  sku: string | null;
  quantity: number | null;
  quote_idn: string;
}

interface Props {
  positions: Position[];
}

export function TabPositions({ positions }: Props) {
  if (positions.length === 0) {
    return <p className="py-8 text-center text-slate-400">Нет запрошенных позиций</p>;
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Наименование</TableHead>
          <TableHead>Бренд</TableHead>
          <TableHead>Артикул</TableHead>
          <TableHead className="text-right">Кол-во</TableHead>
          <TableHead>КП</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {positions.map((p) => (
          <TableRow key={p.id}>
            <TableCell className="font-medium">{p.product_name}</TableCell>
            <TableCell className="text-slate-500">{p.brand ?? "—"}</TableCell>
            <TableCell className="text-slate-500">{p.sku ?? "—"}</TableCell>
            <TableCell className="text-right tabular-nums">{p.quantity ?? "—"}</TableCell>
            <TableCell className="text-blue-600">{p.quote_idn}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
