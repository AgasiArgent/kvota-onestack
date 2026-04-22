import Link from "next/link";
import { FileText, Package } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { LocationChip, type LocationChipLocation } from "@/entities/location";
import { UserAvatarChip, type UserAvatarChipUser } from "@/entities/user";
import { SlaTimerBadge } from "@/shared/ui";
import { cn } from "@/lib/utils";

/**
 * WorkspaceInvoicesTable — the main list on /workspace/logistics and
 * /workspace/customs.
 *
 * Column set varies by:
 *   - domain: "logistics" | "customs"
 *   - viewKind: "my" | "completed" | "all"
 *
 * Data is fetched server-side; this is a dumb render component.
 * Rows are 56px tall (DS §Principles: comfortable density).
 */

export type WorkspaceInvoiceStatus =
  | "in_progress"
  | "awaiting_customer"
  | "completed"
  | "cancelled";

export interface WorkspaceInvoiceRow {
  id: string;
  quoteId: string;
  idn: string; // "Q-202604-0018 / inv-1"
  quoteIdn: string;
  customerName: string;
  pickupLocation: LocationChipLocation;
  deliveryLocation: LocationChipLocation;
  itemsCount: number;
  /** Kilograms — logistics view. */
  totalWeightKg?: number;
  /** "N/M" HS codes filled — customs view. */
  hsCodesFilled?: number;
  hsCodesTotal?: number;
  /** Count of licenses-required items — customs view. */
  licensesRequired?: number;
  assignedAt: string;
  deadlineAt: string;
  completedAt?: string | null;
  assignedUser?: UserAvatarChipUser;
  status: WorkspaceInvoiceStatus;
}

interface WorkspaceInvoicesTableProps {
  domain: "logistics" | "customs";
  viewKind: "my" | "completed" | "all";
  invoices: WorkspaceInvoiceRow[];
  emptyLabel?: string;
}

const STATUS_VARIANT: Record<
  WorkspaceInvoiceStatus,
  { label: string; cls: string }
> = {
  in_progress: { label: "В работе", cls: "bg-warning-bg text-warning border-warning/30" },
  awaiting_customer: {
    label: "Ждём клиента",
    cls: "bg-info-bg text-info border-info/30",
  },
  completed: { label: "Завершено", cls: "bg-success-bg text-success border-success/30" },
  cancelled: { label: "Отменено", cls: "bg-sidebar text-text-muted border-border-light" },
};

function formatKg(kg: number): string {
  if (kg >= 1000) return `${(kg / 1000).toFixed(1)} т`;
  return `${Math.round(kg)} кг`;
}

export function WorkspaceInvoicesTable({
  domain,
  viewKind,
  invoices,
  emptyLabel = "Заявок пока нет",
}: WorkspaceInvoicesTableProps) {
  const showCompletedCol = viewKind === "completed";
  const showAssignedCol = viewKind !== "my"; // on "my", assignee is always self

  if (invoices.length === 0) {
    return (
      <div className="rounded-lg border border-border-light bg-card p-12 text-center">
        <FileText
          size={24}
          strokeWidth={1.5}
          className="mx-auto mb-3 text-text-subtle"
          aria-hidden
        />
        <p className="text-sm text-text-muted">{emptyLabel}</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border-light bg-card overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="bg-sidebar/50 hover:bg-sidebar/50">
            <TableHead className="w-[180px]">Инвойс</TableHead>
            <TableHead className="w-[220px]">Клиент</TableHead>
            <TableHead>Маршрут</TableHead>
            {domain === "logistics" ? (
              <TableHead className="w-[120px] text-right tabular-nums">
                Вес / Поз.
              </TableHead>
            ) : (
              <TableHead className="w-[140px] text-right tabular-nums">
                HS / Лиц.
              </TableHead>
            )}
            {showAssignedCol && (
              <TableHead className="w-[180px]">Исполнитель</TableHead>
            )}
            {showCompletedCol ? (
              <TableHead className="w-[140px]">Завершено</TableHead>
            ) : (
              <TableHead className="w-[140px]">SLA</TableHead>
            )}
            <TableHead className="w-[120px]">Статус</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {invoices.map((inv) => (
            <TableRow key={inv.id} className="h-14 align-middle">
              <TableCell>
                <Link
                  href={`/quotes/${inv.quoteId}?invoice=${inv.id}`}
                  className="text-sm font-medium text-text hover:text-accent transition-colors tabular-nums"
                >
                  {inv.idn}
                </Link>
              </TableCell>
              <TableCell>
                <span className="text-sm text-text truncate block max-w-[200px]">
                  {inv.customerName}
                </span>
              </TableCell>
              <TableCell>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <LocationChip location={inv.pickupLocation} size="sm" />
                  <span className="text-text-subtle text-xs" aria-hidden>
                    →
                  </span>
                  <LocationChip location={inv.deliveryLocation} size="sm" />
                </div>
              </TableCell>
              <TableCell className="text-right tabular-nums text-sm">
                {domain === "logistics" ? (
                  <div className="flex flex-col items-end leading-tight">
                    <span className="text-text">
                      {inv.totalWeightKg != null ? formatKg(inv.totalWeightKg) : "—"}
                    </span>
                    <span className="text-xs text-text-subtle">
                      <Package size={10} className="inline -mt-0.5 mr-0.5" aria-hidden />
                      {inv.itemsCount}
                    </span>
                  </div>
                ) : (
                  <div className="flex flex-col items-end leading-tight">
                    <span
                      className={cn(
                        "text-text",
                        inv.hsCodesFilled !== inv.hsCodesTotal && "text-warning",
                      )}
                    >
                      {inv.hsCodesFilled ?? 0}/{inv.hsCodesTotal ?? 0}
                    </span>
                    {inv.licensesRequired ? (
                      <span className="text-xs text-text-muted">
                        лиц: {inv.licensesRequired}
                      </span>
                    ) : (
                      <span className="text-xs text-text-subtle">без лиц.</span>
                    )}
                  </div>
                )}
              </TableCell>
              {showAssignedCol && (
                <TableCell>
                  {inv.assignedUser ? (
                    <UserAvatarChip user={inv.assignedUser} size="sm" />
                  ) : (
                    <span className="text-xs text-text-subtle italic">не назначен</span>
                  )}
                </TableCell>
              )}
              {showCompletedCol ? (
                <TableCell className="text-sm text-text-muted tabular-nums">
                  {inv.completedAt
                    ? new Date(inv.completedAt).toLocaleDateString("ru-RU", {
                        day: "2-digit",
                        month: "short",
                      })
                    : "—"}
                </TableCell>
              ) : (
                <TableCell>
                  <SlaTimerBadge
                    assignedAt={inv.assignedAt}
                    deadlineAt={inv.deadlineAt}
                    completedAt={inv.completedAt}
                  />
                </TableCell>
              )}
              <TableCell>
                <Badge
                  variant="outline"
                  className={cn("text-xs font-medium", STATUS_VARIANT[inv.status].cls)}
                >
                  {STATUS_VARIANT[inv.status].label}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
