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
import type { LocationType } from "@/entities/location/ui/location-chip";

interface Props {
  locations: LocationListItem[];
}

const TYPE_CONFIG: Record<
  LocationType,
  { label: string; className: string }
> = {
  supplier: {
    label: "Поставщик",
    className: "bg-blue-50 text-blue-700 border-blue-200",
  },
  hub: {
    label: "Хаб",
    className: "bg-violet-50 text-violet-700 border-violet-200",
  },
  customs: {
    label: "Таможня",
    className: "bg-amber-50 text-amber-700 border-amber-200",
  },
  own_warehouse: {
    label: "Склад",
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  client: {
    label: "Клиент",
    className: "bg-rose-50 text-rose-700 border-rose-200",
  },
};

function TypeChip({ type }: { type: LocationType }) {
  const cfg = TYPE_CONFIG[type];
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-2 py-0.5 text-xs font-medium ${cfg.className}`}
    >
      {cfg.label}
    </span>
  );
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
              <TypeChip type={loc.location_type} />
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
