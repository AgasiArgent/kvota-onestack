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

import { useState } from "react";
import type {
  JourneyManifest,
  JourneyNodeId,
  JourneyNodeAggregated,
  RoleSlug,
} from "@/entities/journey";
import { useNodes, canCreateGhost } from "@/entities/journey";
import {
  useJourneyUrlState,
  DEFAULT_LAYERS,
  type JourneyUrlState,
} from "../lib/use-journey-url-state";
import {
  initialFilterState,
  useLayerPersistence,
  type JourneyFilterState,
} from "../lib/use-journey-filter";
import { AppToaster } from "@/shared/ui/app-toaster";
import { JourneyCanvas } from "./canvas";
import { JourneySidebar } from "./sidebar/journey-sidebar";
import { JourneyDrawer } from "./drawer/node-drawer";
import { GhostListManager } from "./ghost";

interface JourneyShellProps {
  manifest: JourneyManifest;
  initialUrlState: JourneyUrlState;
  userId?: string | null;
  /**
   * Current user's held role slugs — fetched server-side and passed through
   * so the drawer's inline-edit controls (Task 19) can gate per field ACL.
   */
  userRoles?: readonly RoleSlug[];
}

export function JourneyShell({
  manifest,
  initialUrlState,
  userId = null,
  userRoles = [],
}: JourneyShellProps) {
  const isAdmin = canCreateGhost(userRoles);
  // `initialUrlState` is seeded into the URL by the Server Component; the
  // client hook reads back the same values from `useSearchParams`, so we
  // don't need to thread `initialUrlState` through further — it exists as
  // a prop to make SSR hydration intent explicit and for future use once
  // React Flow needs an authoritative initial mount state.
  const { state, setNode, setLayers, setViewAs } = useJourneyUrlState();
  const drawerOpen = state.node !== null;
  const nodesQuery = useNodes();

  // Sidebar search + cluster list need node data. Use the live query when
  // available; fall back to the static manifest shape during initial load.
  const sidebarNodes: readonly JourneyNodeAggregated[] =
    nodesQuery.data ??
    manifest.nodes.map((n) => ({
      node_id: n.node_id,
      route: n.route,
      title: n.title,
      cluster: n.cluster,
      roles: n.roles,
      impl_status: null,
      qa_status: null,
      version: 0,
      stories_count: n.stories.length,
      feedback_count: 0,
      pins_count: 0,
      ghost_status: null,
      proposed_route: null,
      updated_at: null,
    }));

  // Filter state owned by the shell. Layers + viewAs are mirrored to the
  // URL via `useJourneyUrlState` (primary filter state per Req 3.11);
  // cluster/status/search exclusions are session-scoped only.
  const [filterState, setFilterState] = useState<JourneyFilterState>(() => ({
    ...initialFilterState(),
    layers: state.layers,
    viewAs: state.viewAs,
  }));

  // Hydrate layers from localStorage on mount unless URL carries them
  // (Req 4.9 — URL takes precedence over localStorage on page load).
  // `decodeFromSearchParams` returns the `DEFAULT_LAYERS` reference when the
  // `?layers=` param is absent, so identity comparison reliably detects
  // whether the user loaded with an explicit filter.
  const urlHasExplicitLayers = initialUrlState.layers !== DEFAULT_LAYERS;
  useLayerPersistence({
    userId,
    urlHasExplicitLayers,
    currentLayers: filterState.layers,
    onHydrate: (hydrated) => {
      setFilterState((prev) => ({ ...prev, layers: hydrated }));
      setLayers(hydrated);
    },
  });

  const handleFilterStateChange = (next: JourneyFilterState) => {
    setFilterState(next);
    if (next.layers !== filterState.layers) setLayers(next.layers);
    if (next.viewAs !== filterState.viewAs) setViewAs(next.viewAs);
  };

  return (
    <div
      data-testid="journey-shell"
      className="flex h-[calc(100vh-theme(spacing.12))] min-h-0 gap-0 overflow-hidden"
    >
      <aside
        data-testid="journey-sidebar"
        className="w-[300px] shrink-0 border-r border-border-light bg-sidebar overflow-y-auto"
      >
        <JourneySidebar
          nodes={sidebarNodes}
          state={filterState}
          onStateChange={handleFilterStateChange}
          userId={userId}
          headerSlot={
            isAdmin && userId ? <GhostListManager userId={userId} /> : null
          }
        />
      </aside>

      <section
        data-testid="journey-canvas"
        className="relative flex-1 min-w-0 bg-background"
      >
        {nodesQuery.isLoading && (
          <div className="flex h-full items-center justify-center text-sm text-text-subtle">
            Загрузка карты… · Узлов в манифесте: {manifest.nodes.length}
          </div>
        )}
        {nodesQuery.isError && (
          <div className="flex h-full items-center justify-center p-6 text-center text-sm text-error">
            Не удалось загрузить данные узлов. Попробуйте обновить страницу.
          </div>
        )}
        {nodesQuery.data && (
          <JourneyCanvas
            nodes={nodesQuery.data}
            edges={[]}
            selectedNodeId={state.node}
            onSelectNode={(id) => setNode(id as JourneyNodeId | null)}
          />
        )}
      </section>

      {drawerOpen && (
        <JourneyDrawer
          nodeId={state.node}
          onClose={() => setNode(null)}
          userRoles={userRoles}
          userId={userId ?? undefined}
        />
      )}

      <AppToaster />
    </div>
  );
}
