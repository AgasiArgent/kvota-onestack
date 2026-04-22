"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { UserPlus, AlertCircle, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { LocationChip, type LocationChipLocation } from "@/entities/location";
import { UserAvatarChip, type UserAvatarChipUser } from "@/entities/user";
import { SlaTimerBadge } from "@/shared/ui";
import { reassignInvoice } from "../server-actions";
import { cn } from "@/lib/utils";

/**
 * UnassignedInbox — head-only list of invoices with no assignee.
 *
 * Each row is a card (not a table row) to make the "Назначить" dropdown
 * action prominent. Click the button → Popover with user search → select →
 * Server Action assigns + router.refresh().
 *
 * Appears on /workspace/logistics and /workspace/customs when the current
 * user is head_of_logistics / head_of_customs / admin.
 */

export interface UnassignedInvoiceRow {
  id: string;
  quoteId: string;
  idn: string;
  customerName: string;
  pickupLocation: LocationChipLocation;
  deliveryLocation: LocationChipLocation;
  itemsCount: number;
  totalWeightKg?: number;
  createdAt: string;
  deadlineAt: string;
  /** Patterns that would have auto-routed this, if any. */
  suggestedUsers?: UserAvatarChipUser[];
}

interface UnassignedInboxProps {
  domain: "logistics" | "customs";
  invoices: UnassignedInvoiceRow[];
  teamUsers: UserAvatarChipUser[];
}

export function UnassignedInbox({
  domain,
  invoices,
  teamUsers,
}: UnassignedInboxProps) {
  if (invoices.length === 0) {
    return (
      <div className="rounded-lg border border-border-light bg-card p-12 text-center">
        <AlertCircle
          size={24}
          strokeWidth={1.5}
          className="mx-auto mb-3 text-success"
          aria-hidden
        />
        <p className="text-sm text-text">Все заявки распределены</p>
        <p className="text-xs text-text-muted mt-1">Нет инвойсов без исполнителя</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <header className="flex items-center gap-2 px-1">
        <AlertCircle size={14} strokeWidth={2} className="text-warning" aria-hidden />
        <h2 className="text-sm font-medium text-text">
          Требуют распределения — {invoices.length}
        </h2>
      </header>
      {invoices.map((inv) => (
        <UnassignedRow
          key={inv.id}
          domain={domain}
          invoice={inv}
          teamUsers={teamUsers}
        />
      ))}
    </div>
  );
}

function UnassignedRow({
  domain,
  invoice,
  teamUsers,
}: {
  domain: "logistics" | "customs";
  invoice: UnassignedInvoiceRow;
  teamUsers: UserAvatarChipUser[];
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  const filtered = teamUsers.filter((u) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return (
      u.name.toLowerCase().includes(q) ||
      (u.email?.toLowerCase().includes(q) ?? false)
    );
  });

  const handleAssign = (userId: string) => {
    setError(null);
    startTransition(async () => {
      try {
        await reassignInvoice(invoice.id, domain, userId);
        setOpen(false);
        router.refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Не удалось назначить");
      }
    });
  };

  return (
    <article
      className={cn(
        "rounded-lg border border-warning/30 bg-warning-bg/30 p-4",
        "grid grid-cols-[1fr_auto] gap-4 items-center",
      )}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-3 mb-1.5 flex-wrap">
          <Link
            href={`/quotes/${invoice.quoteId}?invoice=${invoice.id}`}
            className="text-sm font-semibold text-text hover:text-accent tabular-nums"
          >
            {invoice.idn}
          </Link>
          <span className="text-sm text-text-muted truncate">
            {invoice.customerName}
          </span>
          <SlaTimerBadge
            assignedAt={invoice.createdAt}
            deadlineAt={invoice.deadlineAt}
          />
        </div>
        <div className="flex items-center gap-1.5 flex-wrap text-xs">
          <LocationChip location={invoice.pickupLocation} size="sm" />
          <span className="text-text-subtle" aria-hidden>→</span>
          <LocationChip location={invoice.deliveryLocation} size="sm" />
          <span className="text-text-muted tabular-nums ml-2">
            {invoice.itemsCount} поз.
            {invoice.totalWeightKg != null
              ? ` · ${Math.round(invoice.totalWeightKg)} кг`
              : ""}
          </span>
        </div>
        {invoice.suggestedUsers && invoice.suggestedUsers.length > 0 && (
          <div className="mt-2 flex items-center gap-2 text-xs text-text-muted">
            <span>Рекомендуем:</span>
            {invoice.suggestedUsers.slice(0, 3).map((u) => (
              <button
                key={u.id}
                type="button"
                onClick={() => handleAssign(u.id)}
                disabled={isPending}
                className="hover:underline disabled:opacity-50"
              >
                <UserAvatarChip user={u} size="xs" />
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-col items-end gap-1">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger
            render={
              <Button
                size="sm"
                variant="default"
                disabled={isPending}
                className="gap-1.5"
              />
            }
          >
            <UserPlus size={14} strokeWidth={2} aria-hidden />
            Назначить {domain === "logistics" ? "логиста" : "таможенника"}
          </PopoverTrigger>
          <PopoverContent align="end" className="w-72 p-0" sideOffset={4}>
            <div className="border-b border-border-light p-2">
              <div className="relative">
                <Search
                  size={12}
                  strokeWidth={2}
                  className="absolute left-2 top-1/2 -translate-y-1/2 text-text-subtle"
                  aria-hidden
                />
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Поиск..."
                  className="h-8 pl-7 text-sm"
                  autoFocus
                />
              </div>
            </div>
            <div className="max-h-64 overflow-y-auto p-1">
              {filtered.length === 0 ? (
                <div className="px-3 py-4 text-xs text-text-subtle text-center">
                  Никого не найдено
                </div>
              ) : (
                filtered.map((u) => (
                  <button
                    key={u.id}
                    type="button"
                    onClick={() => handleAssign(u.id)}
                    disabled={isPending}
                    className={cn(
                      "w-full text-left rounded-sm px-2 py-1.5",
                      "hover:bg-sidebar transition-colors",
                      "disabled:opacity-50",
                    )}
                  >
                    <UserAvatarChip user={u} size="sm" showEmail />
                  </button>
                ))
              )}
            </div>
          </PopoverContent>
        </Popover>
        {error && (
          <span className="text-xs text-error" role="alert">
            {error}
          </span>
        )}
      </div>
    </article>
  );
}
