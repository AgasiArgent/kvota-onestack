"use client";

/**
 * Three-pane shell for `/journey`.
 *
 *   ┌───────────────┬────────────────────────────┬──────────────────────┐
 *   │  Left sidebar │  Center canvas             │  Right drawer        │
 *   │  (layers +    │  (React Flow in Task 16 —  │  (node detail in     │
 *   │   filters,    │   placeholder for now)     │   Task 17 — shown    │
 *   │   Task 18)    │                            │   when node set)     │
 *   └───────────────┴────────────────────────────┴──────────────────────┘
 *
 * Responsibilities:
 *   - Seed client-side URL state from `initialUrlState` (SSR-parsed).
 *   - Render the three pane placeholders with `data-testid` hooks so Task
 *     16–18 implementations can drop in without changing the shell.
 *   - Pass current state through to placeholders so they can show it
 *     (debug-only during Group B; replaced by real UI in Group C).
 *
 * Reqs: 3.1 (page layout), 3.2 (sidebar visible), 3.10 (state restored
 * from URL on load), 3.11 (sidebar entry — handled in widgets/sidebar).
 */

import type { JourneyManifest } from "@/entities/journey";
import { useJourneyUrlState, type JourneyUrlState } from "../lib/use-journey-url-state";

interface JourneyShellProps {
  manifest: JourneyManifest;
  initialUrlState: JourneyUrlState;
}

export function JourneyShell({ manifest }: JourneyShellProps) {
  // `initialUrlState` is seeded into the URL by the Server Component; the
  // client hook reads back the same values from `useSearchParams`, so we
  // don't need to thread `initialUrlState` through further — it exists as
  // a prop to make SSR hydration intent explicit and for future use once
  // React Flow needs an authoritative initial mount state.
  const { state } = useJourneyUrlState();
  const drawerOpen = state.node !== null;

  return (
    <div
      data-testid="journey-shell"
      className="flex h-[calc(100vh-theme(spacing.12))] min-h-0 gap-0 overflow-hidden"
    >
      <aside
        data-testid="journey-sidebar"
        className="w-[300px] shrink-0 border-r border-border-light bg-sidebar overflow-y-auto"
      >
        <div className="p-4 text-sm text-text-muted">
          <p className="mb-2 font-medium text-text">Слои и фильтры</p>
          <p className="text-xs text-text-subtle">
            Task 18 добавит переключатели слоёв и фильтры. Сейчас активны:{" "}
            <span data-testid="journey-active-layers">
              {state.layers.length > 0 ? state.layers.join(", ") : "—"}
            </span>
          </p>
          {state.viewAs && (
            <p
              data-testid="journey-viewas-badge"
              className="mt-2 inline-flex items-center rounded-md bg-accent-subtle px-2 py-0.5 text-xs font-medium text-accent"
            >
              View as: {state.viewAs}
            </p>
          )}
        </div>
      </aside>

      <section
        data-testid="journey-canvas"
        className="relative flex-1 min-w-0 bg-background"
      >
        <div className="flex h-full items-center justify-center text-text-subtle">
          <div className="text-center">
            <p className="text-base font-medium text-text">Карта путей</p>
            <p className="mt-1 text-sm">
              Canvas появится в Task 16 · Узлов в манифесте: {manifest.nodes.length}
            </p>
          </div>
        </div>
      </section>

      {drawerOpen && (
        <aside
          data-testid="journey-drawer"
          className="w-[400px] shrink-0 border-l border-border-light bg-sidebar overflow-y-auto"
        >
          <div className="p-4 text-sm text-text-muted">
            <p className="mb-2 font-medium text-text">Детали узла</p>
            <p
              data-testid="journey-drawer-node-id"
              className="break-all rounded-md bg-background px-2 py-1 text-xs font-mono"
            >
              {state.node}
            </p>
            <p className="mt-3 text-xs text-text-subtle">
              Task 17 добавит подробную карточку.
            </p>
          </div>
        </aside>
      )}
    </div>
  );
}
