"use client";

/**
 * Left sidebar for `/journey` — layer toggles + filters + search.
 *
 * Sections (top-to-bottom, per Req 3.3):
 *   1. Layer toggles
 *   2. "View as role"
 *   3. Impl-status filter
 *   4. QA-status filter
 *   5. Search
 *   6. Cluster multi-select
 *
 * State flow: parent owns `JourneyFilterState` and passes it down with a
 * setter. The sidebar dispatches state transitions via the pure helpers in
 * `use-journey-filter.ts` (toggleLayer / toggleExclusion), so the component
 * never mutates props.
 *
 * localStorage persistence for layers is attached here: every layer change
 * writes to `journey:layers:{userId}` (Req 4.9). Hydration happens in the
 * shell, which passes the hydrated layers down through `state.layers`.
 */

import type React from "react";
import {
  toggleExclusion,
  toggleLayer,
  writeLayersToStorage,
  type JourneyFilterState,
  type ImplFilterValue,
  type QaFilterValue,
} from "../../lib/use-journey-filter";
import type { LayerId } from "../../lib/use-journey-url-state";
import type {
  JourneyNodeAggregated,
  RoleSlug,
} from "@/entities/journey";
import { LayerToggles } from "./layer-toggles";
import { ViewAsRole } from "./view-as-role";
import { JourneySearch } from "./search";
import { ClusterMultiselect } from "./cluster-multiselect";
import { ImplStatusFilter, QaStatusFilter } from "./status-filters";

interface Props {
  readonly nodes: readonly JourneyNodeAggregated[];
  readonly state: JourneyFilterState;
  readonly onStateChange: (next: JourneyFilterState) => void;
  readonly userId: string | null;
  /** Optional slot rendered above filters (e.g. admin "+ Ghost" button). */
  readonly headerSlot?: React.ReactNode;
}

export function JourneySidebar({
  nodes,
  state,
  onStateChange,
  userId,
  headerSlot,
}: Props) {
  const handleLayerToggle = (layer: LayerId) => {
    const next = toggleLayer(state.layers, layer);
    onStateChange({ ...state, layers: next });
    writeLayersToStorage(userId, next);
  };

  const handleViewAs = (viewAs: RoleSlug | null) => {
    onStateChange({ ...state, viewAs });
  };

  const handleClusterToggle = (cluster: string) => {
    onStateChange({
      ...state,
      clustersExcluded: toggleExclusion(state.clustersExcluded, cluster),
    });
  };

  const handleImplToggle = (value: ImplFilterValue) => {
    onStateChange({
      ...state,
      implStatusesExcluded: toggleExclusion(state.implStatusesExcluded, value),
    });
  };

  const handleQaToggle = (value: QaFilterValue) => {
    onStateChange({
      ...state,
      qaStatusesExcluded: toggleExclusion(state.qaStatusesExcluded, value),
    });
  };

  const handleSearch = (search: string) => {
    onStateChange({ ...state, search });
  };

  return (
    <div
      data-testid="journey-sidebar-content"
      className="flex h-full flex-col gap-5 p-4"
    >
      {headerSlot ? <section>{headerSlot}</section> : null}
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
          Слои
        </h3>
        <LayerToggles
          activeLayers={state.layers}
          onToggle={handleLayerToggle}
        />
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
          Фильтры
        </h3>
        <div className="flex flex-col gap-4">
          <ViewAsRole value={state.viewAs} onChange={handleViewAs} />
          <ImplStatusFilter
            excluded={state.implStatusesExcluded}
            onToggle={handleImplToggle}
          />
          <QaStatusFilter
            excluded={state.qaStatusesExcluded}
            onToggle={handleQaToggle}
          />
        </div>
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-subtle">
          Поиск
        </h3>
        <JourneySearch value={state.search} onChange={handleSearch} />
      </section>

      <section>
        <ClusterMultiselect
          nodes={nodes}
          excluded={state.clustersExcluded}
          onToggle={handleClusterToggle}
        />
      </section>
    </div>
  );
}
