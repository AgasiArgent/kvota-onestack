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
  fetchPauseHistory,
  type PauseHistoryEntry,
} from "@/entities/quote/mutations";

export interface PauseHistoryPanelProps {
  open: boolean;
  quoteId: string | null;
  quoteIdn: string | null;
  onClose: () => void;
}

/**
 * Read-only timeline of pause/unpause activity for a quote (Testing 2 row
 * 74). Fetched lazily on open; empty list renders a friendly empty state.
 *
 * Each entry shows: paused_at, paused_by, reason, unpaused_at + unpaused_by
 * (if closed). Open entries (unpaused_at IS NULL) are marked «Активна».
 */
export function PauseHistoryPanel({
  open,
  quoteId,
  quoteIdn,
  onClose,
}: PauseHistoryPanelProps) {
  // State keyed to the loaded quote so stale results don't flash when the
  // user opens the panel for a different quote before the fetch resolves.
  const [loaded, setLoaded] = useState<{
    quoteId: string;
    entries: PauseHistoryEntry[];
  } | null>(null);

  useEffect(() => {
    if (!open || !quoteId) return;
    let cancelled = false;
    fetchPauseHistory(quoteId).then((list) => {
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
          <DialogTitle>История пауз {quoteIdn ?? ""}</DialogTitle>
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
              <PauseHistoryItem key={entry.id} entry={entry} />
            ))}
          </ol>
        )}
      </DialogContent>
    </Dialog>
  );
}

function PauseHistoryItem({ entry }: { entry: PauseHistoryEntry }) {
  const isActive = entry.unpaused_at === null;
  return (
    <li className="rounded-md border border-border p-3 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">
          {formatDateTime(entry.paused_at)}
          {entry.paused_by_name ? ` — ${entry.paused_by_name}` : ""}
        </span>
        <span
          className={[
            "rounded-full px-2 py-0.5 text-xs",
            isActive
              ? "bg-amber-100 text-amber-800"
              : "bg-muted text-muted-foreground",
          ].join(" ")}
        >
          {isActive ? "Активна" : "Завершена"}
        </span>
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm">{entry.reason}</p>
      {entry.unpaused_at && (
        <p className="mt-2 text-xs text-muted-foreground">
          Снято с паузы: {formatDateTime(entry.unpaused_at)}
          {entry.unpaused_by_name ? ` — ${entry.unpaused_by_name}` : ""}
        </p>
      )}
    </li>
  );
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
