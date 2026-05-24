"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { deleteLocation } from "@/entities/location/server-actions";
import type { LocationListItem } from "../model/types";
import { LocationTypeCell } from "./location-type-cell";

interface Props {
  locations: LocationListItem[];
  canEditType?: boolean;
  /**
   * Whether the current viewer can delete locations. Same role gate as
   * `canEditType` in practice (admin / head_of_logistics / head_of_customs)
   * but separated so callers can disable the column independently.
   */
  canDelete?: boolean;
}

export function LocationsTable({
  locations,
  canEditType = false,
  canDelete = false,
}: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[100px]">Код</TableHead>
          <TableHead>Город</TableHead>
          <TableHead>Страна</TableHead>
          <TableHead>Тип</TableHead>
          <TableHead>Статус</TableHead>
          {canDelete && <TableHead className="w-[60px]" />}
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
            {canDelete && (
              <TableCell>
                <DeleteLocationButton location={loc} />
              </TableCell>
            )}
          </TableRow>
        ))}
        {locations.length === 0 && (
          <TableRow>
            <TableCell
              colSpan={canDelete ? 6 : 5}
              className="text-center py-8 text-text-subtle"
            >
              Локации не найдены
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}

/**
 * Inline delete button. Confirms via `window.confirm` (low-frequency action,
 * a full dialog would be overkill). Toast surfaces the «used in N КП»
 * message the server returns so the head knows what's blocking.
 */
function DeleteLocationButton({ location }: { location: LocationListItem }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const label = location.code
    ? `${location.code} (${location.country}${location.city ? `, ${location.city}` : ""})`
    : `${location.country}${location.city ? `, ${location.city}` : ""}`;

  function handleClick() {
    const ok = window.confirm(`Удалить локацию «${label}»?`);
    if (!ok) return;

    startTransition(async () => {
      const result = await deleteLocation(location.id);
      if (result.success) {
        toast.success("Локация удалена");
        router.refresh();
        return;
      }
      if (result.usage && result.usage.length > 0) {
        // «КП поставщиков (3), сегменты маршрутов (откуда) (1)» — the head
        // can chase down the references and reroute them before retrying.
        const parts = result.usage.map(
          (u) => `${u.label} (${u.count})`,
        );
        toast.error(
          `Нельзя удалить — локация используется: ${parts.join(", ")}`,
        );
        return;
      }
      toast.error(result.error ?? "Не удалось удалить локацию");
    });
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      disabled={isPending}
      onClick={handleClick}
      aria-label="Удалить локацию"
      title="Удалить локацию"
      className="text-text-subtle hover:text-destructive"
    >
      <Trash2 size={14} />
    </Button>
  );
}
