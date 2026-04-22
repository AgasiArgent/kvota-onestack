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
import { LocationTypeCell } from "./location-type-cell";

interface Props {
  locations: LocationListItem[];
  canEditType?: boolean;
}

export function LocationsTable({ locations, canEditType = false }: Props) {
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
              <LocationTypeCell
                locationId={loc.id}
                type={loc.location_type}
                canEdit={canEditType}
              />
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
