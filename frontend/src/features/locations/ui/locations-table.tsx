"use client";

import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { LocationListItem } from "../model/types";

interface Props {
  locations: LocationListItem[];
}

function TypeBadges({ location }: { location: LocationListItem }) {
  const badges: React.ReactNode[] = [];
  if (location.is_hub) {
    badges.push(
      <Badge key="hub" variant="default" className="text-xs">
        Хаб
      </Badge>
    );
  }
  if (location.is_customs_point) {
    badges.push(
      <Badge key="customs" variant="secondary" className="text-xs">
        Таможня
      </Badge>
    );
  }
  if (badges.length === 0) return <span className="text-text-subtle">&mdash;</span>;
  return <div className="flex gap-1">{badges}</div>;
}

export function LocationsTable({ locations }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[100px]">Код</TableHead>
          <TableHead>Город</TableHead>
          <TableHead>Страна</TableHead>
          <TableHead>Тип</TableHead>
          <TableHead>Статус</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {locations.map((loc) => (
          <TableRow key={loc.id}>
            <TableCell className="font-mono text-sm tabular-nums">
              {loc.code ?? <span className="text-text-subtle">&mdash;</span>}
            </TableCell>
            <TableCell>{loc.city ?? <span className="text-text-subtle">&mdash;</span>}</TableCell>
            <TableCell className="text-text-muted">{loc.country}</TableCell>
            <TableCell>
              <TypeBadges location={loc} />
            </TableCell>
            <TableCell>
              <Badge variant={loc.is_active ? "default" : "secondary"}>
                {loc.is_active ? "Активна" : "Неактивна"}
              </Badge>
            </TableCell>
          </TableRow>
        ))}
        {locations.length === 0 && (
          <TableRow>
            <TableCell colSpan={5} className="text-center py-8 text-text-subtle">
              Локации не найдены
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
