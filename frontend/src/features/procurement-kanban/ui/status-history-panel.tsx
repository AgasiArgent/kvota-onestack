"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  fetchStatusHistory,
  type StatusHistoryEntry,
} from "@/entities/quote/mutations";
import {
  SUBSTATUS_LABELS_RU,
  isProcurementSubstatus,
} from "@/shared/lib/workflow-substates";

export interface StatusHistoryPanelProps {
  open: boolean;
  quoteId: string | null;
  quoteIdn: string | null;
  onClose: () => void;
}

/**
 * Read-only timeline of substatus transitions for a quote. Fetched on open;
 * empty list renders a friendly empty state. No editing — audit-only.
 */
export function StatusHistoryPanel({
  open,
  quoteId,
  quoteIdn,
  onClose,
}: StatusHistoryPanelProps) {
  // State keyed to the loaded quote so stale results don't flash when the
  // user opens the panel for a different quote before the fetch resolves.
  const [loaded, setLoaded] = useState<{
    quoteId: string;
    entries: StatusHistoryEntry[];
  } | null>(null);

  useEffect(() => {
    if (!open || !quoteId) return;
    let cancelled = false;
    fetchStatusHistory(quoteId).then((list) => {
      if (!cancelled) setLoaded({ quoteId, entries: list });
    });
    return () => {
      cancelled = true;
    };
  }, [open, quoteId]);

  const loading = open && quoteId !== null && loaded?.quoteId !== quoteId;
  const entries = loaded?.quoteId === quoteId ? loaded.entries : [];

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen) onClose();
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>История статусов {quoteIdn ?? ""}</DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
          </div>
        ) : entries.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            История пуста
          </p>
        ) : (
          <ol className="flex flex-col gap-3">
            {entries.map((entry) => (
              <li
                key={entry.id}
                className="rounded-md border border-border p-3 text-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">
                    {renderTransitionLabel(entry)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {formatDateTime(entry.transitioned_at)}
                  </span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {entry.transitioned_by_name ?? "Система"}
                </div>
                {entry.reason && (
                  <p className="mt-2 whitespace-pre-wrap text-sm">
                    {entry.reason}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </DialogContent>
    </Dialog>
  );
}

function renderTransitionLabel(entry: StatusHistoryEntry): string {
  const from = entry.from_substatus;
  const to = entry.to_substatus;
  const fromLabel =
    from && isProcurementSubstatus(from) ? SUBSTATUS_LABELS_RU[from] : from;
  const toLabel =
    to && isProcurementSubstatus(to) ? SUBSTATUS_LABELS_RU[to] : to;

  if (fromLabel && toLabel) return `${fromLabel} → ${toLabel}`;
  if (toLabel) return `→ ${toLabel}`;
  // Workflow-level transition (no substatus).
  return `${entry.from_status ?? "—"} → ${entry.to_status}`;
}

function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
