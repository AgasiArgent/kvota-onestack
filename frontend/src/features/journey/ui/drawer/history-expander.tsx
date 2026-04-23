"use client";

/**
 * History expander (Req 5.7). Collapsed by default; expanding it triggers
 * the `useNodeHistory` fetch (TanStack Query is lazy by default — we gate
 * the hook call on the expanded state so the network request only fires
 * when the user clicks).
 *
 * Renders in reverse-chronological order (Req 5.7). Server already orders
 * `changed_at DESC` in `GET /api/journey/node/{id}/history`.
 */

import { useState } from "react";
import { useNodeHistory } from "@/entities/journey";
import type { JourneyNodeId } from "@/entities/journey";

export interface HistoryExpanderProps {
  readonly nodeId: JourneyNodeId;
}

function HistoryBody({ nodeId }: { nodeId: JourneyNodeId }) {
  const query = useNodeHistory(nodeId);
  if (query.isLoading) {
    return <p className="text-xs text-text-subtle">Загрузка истории…</p>;
  }
  if (query.isError) {
    return (
      <p className="text-xs text-destructive" role="alert">
        Не удалось загрузить историю.
      </p>
    );
  }
  const rows = query.data ?? [];
  if (rows.length === 0) {
    return <p className="text-xs text-text-subtle">История пуста</p>;
  }
  return (
    <ol className="space-y-1.5">
      {rows.map((row) => (
        <li
          key={row.id}
          className="rounded-md border border-border-light bg-background p-2 text-xs"
        >
          <div className="flex items-center justify-between text-text-subtle">
            <span>{new Date(row.changed_at).toLocaleString("ru-RU")}</span>
            <span>v{row.version}</span>
          </div>
          <p className="mt-0.5 text-text">
            {row.impl_status && <>Реализация: {row.impl_status} · </>}
            {row.qa_status && <>QA: {row.qa_status}</>}
          </p>
          {row.changed_by && (
            <p className="mt-0.5 text-text-subtle">Автор: {row.changed_by}</p>
          )}
        </li>
      ))}
    </ol>
  );
}

export function HistoryExpander({ nodeId }: HistoryExpanderProps) {
  const [open, setOpen] = useState(false);
  return (
    <section
      data-testid="history-expander"
      className="p-4"
      aria-label="История изменений"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="text-xs font-semibold uppercase tracking-wide text-text-subtle hover:text-text"
      >
        История изменений {open ? "▾" : "▸"}
      </button>
      {open && (
        <div className="mt-2" data-testid="history-expander-body">
          <HistoryBody nodeId={nodeId} />
        </div>
      )}
    </section>
  );
}
