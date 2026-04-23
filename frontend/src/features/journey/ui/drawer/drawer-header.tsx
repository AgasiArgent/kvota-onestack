"use client";

/**
 * Header row of the drawer: title, cluster, route, close button.
 * (Req 5.1 — the section containing route path + title.)
 */

import type { JourneyNodeDetail } from "@/entities/journey";

export interface DrawerHeaderProps {
  readonly detail: JourneyNodeDetail;
  readonly onClose: () => void;
}

export function DrawerHeader({ detail, onClose }: DrawerHeaderProps) {
  return (
    <header
      data-testid="drawer-header"
      className="flex items-start justify-between gap-3 p-4"
    >
      <div className="min-w-0">
        <p className="text-xs uppercase tracking-wide text-text-subtle">
          {detail.cluster}
        </p>
        <h2 className="mt-1 truncate text-base font-semibold text-text">
          {detail.title}
        </h2>
        <p className="mt-1 break-all rounded-md bg-background px-2 py-0.5 text-xs font-mono text-text-muted">
          {detail.route}
        </p>
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label="Закрыть"
        className="rounded-md p-1 text-text-muted hover:bg-background hover:text-text"
      >
        ×
      </button>
    </header>
  );
}
