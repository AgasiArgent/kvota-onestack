"use client";

/**
 * Journey sidebar filter engine.
 *
 * Pure helpers + a hook for persisting layer toggles to localStorage.
 *
 * Filter model:
 *   - `layers`              — eight canonical layer IDs (Req 4.1).
 *   - `viewAs`              — role slug; when set, only nodes whose `roles`
 *                              include this slug remain visible (Req 3.4).
 *   - `clustersExcluded`    — cluster IDs the user has toggled off.
 *   - `implStatusesExcluded` — impl status values the user has toggled off
 *                              (Req 4.10 derivative — status-filter sidebar).
 *   - `qaStatusesExcluded`   — same for qa_status.
 *   - `search`              — case-insensitive substring query (Req 3.5).
 *                              Non-matches FADE but stay on canvas.
 *
 * `applyJourneyFilters` returns two ReadonlySets:
 *   - `visibleIds` — pass all hard filters (role / cluster / impl / qa).
 *   - `fadedIds`   — a subset of `visibleIds` that does NOT match the search.
 *
 * Hidden nodes never appear in `fadedIds` (you cannot fade what isn't rendered).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  JourneyNodeAggregated,
  JourneyNodeId,
  RoleSlug,
} from "@/entities/journey";
import {
  ALL_LAYER_IDS,
  DEFAULT_LAYERS,
  type LayerId,
} from "./use-journey-url-state";

// ---------------------------------------------------------------------------
// Filter state shape
// ---------------------------------------------------------------------------

export type ImplFilterValue = "done" | "partial" | "missing" | "unset";
export type QaFilterValue = "verified" | "broken" | "untested" | "unset";

export const ALL_IMPL_FILTER_VALUES: readonly ImplFilterValue[] = [
  "done",
  "partial",
  "missing",
  "unset",
];

export const ALL_QA_FILTER_VALUES: readonly QaFilterValue[] = [
  "verified",
  "broken",
  "untested",
  "unset",
];

export interface JourneyFilterState {
  readonly layers: readonly LayerId[];
  readonly viewAs: RoleSlug | null;
  readonly clustersExcluded: readonly string[];
  readonly implStatusesExcluded: readonly ImplFilterValue[];
  readonly qaStatusesExcluded: readonly QaFilterValue[];
  readonly search: string;
}

export function initialFilterState(): JourneyFilterState {
  return {
    layers: DEFAULT_LAYERS,
    viewAs: null,
    clustersExcluded: [],
    implStatusesExcluded: [],
    qaStatusesExcluded: [],
    search: "",
  };
}

// ---------------------------------------------------------------------------
// Pure state transitions
// ---------------------------------------------------------------------------

/**
 * Toggle `layer` in the given list. Returns a new array; preserves the
 * canonical ordering from `ALL_LAYER_IDS` so the UI never sees shuffled rows.
 */
export function toggleLayer(
  layers: readonly LayerId[],
  layer: LayerId,
): readonly LayerId[] {
  const set = new Set<LayerId>(layers);
  if (set.has(layer)) {
    set.delete(layer);
  } else {
    set.add(layer);
  }
  return ALL_LAYER_IDS.filter((l) => set.has(l));
}

/**
 * Toggle a value in an exclusion list (add if absent, remove if present).
 * Generic so it works for cluster slugs, impl statuses, and qa statuses.
 */
export function toggleExclusion<T>(list: readonly T[], value: T): readonly T[] {
  const idx = list.indexOf(value);
  if (idx === -1) {
    return [...list, value];
  }
  return list.slice(0, idx).concat(list.slice(idx + 1));
}

// ---------------------------------------------------------------------------
// applyJourneyFilters
// ---------------------------------------------------------------------------

export interface FilterResult {
  readonly visibleIds: ReadonlySet<JourneyNodeId>;
  readonly fadedIds: ReadonlySet<JourneyNodeId>;
}

function matchesSearch(
  node: JourneyNodeAggregated,
  query: string,
): boolean {
  // Search haystack: route, title, proposed_route (for ghosts), node_id.
  // Story text and pin `expected_behavior` are not yet on the aggregated
  // payload — they will fold in when the backend returns them; the test
  // surface is the pure function, so adding fields later is additive.
  const parts = [
    node.route,
    node.title,
    node.proposed_route ?? "",
    node.node_id,
  ];
  const haystack = parts.join("  ").toLowerCase();
  return haystack.includes(query);
}

export function applyJourneyFilters(
  nodes: readonly JourneyNodeAggregated[],
  state: JourneyFilterState,
): FilterResult {
  const visibleIds = new Set<JourneyNodeId>();
  const fadedIds = new Set<JourneyNodeId>();

  const query = state.search.trim().toLowerCase();
  const hasSearch = query.length > 0;

  for (const node of nodes) {
    // --- Hard filters ---
    if (state.viewAs !== null) {
      if (!node.roles.includes(state.viewAs)) continue;
    }
    if (state.clustersExcluded.includes(node.cluster)) continue;

    const implKey: ImplFilterValue = node.impl_status ?? "unset";
    if (state.implStatusesExcluded.includes(implKey)) continue;

    const qaKey: QaFilterValue = node.qa_status ?? "unset";
    if (state.qaStatusesExcluded.includes(qaKey)) continue;

    visibleIds.add(node.node_id);

    // --- Search fade (only on visible nodes) ---
    if (hasSearch && !matchesSearch(node, query)) {
      fadedIds.add(node.node_id);
    }
  }

  return { visibleIds, fadedIds };
}

// ---------------------------------------------------------------------------
// localStorage persistence (Req 4.9)
// ---------------------------------------------------------------------------

export function storageKeyForUser(userId: string | null): string {
  return `journey:layers:${userId ?? "anonymous"}`;
}

const KNOWN_LAYERS: ReadonlySet<string> = new Set(ALL_LAYER_IDS);

function safeLocalStorage(): Storage | null {
  try {
    // Guard for SSR and hostile test envs where localStorage is unset.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ls = (globalThis as any).localStorage as Storage | undefined;
    return ls ?? null;
  } catch {
    return null;
  }
}

export function readLayersFromStorage(
  userId: string | null,
): readonly LayerId[] | null {
  const ls = safeLocalStorage();
  if (!ls) return null;
  const raw = ls.getItem(storageKeyForUser(userId));
  if (raw === null) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!Array.isArray(parsed)) return null;
  const filtered = parsed.filter(
    (v): v is LayerId => typeof v === "string" && KNOWN_LAYERS.has(v),
  );
  return filtered;
}

export function writeLayersToStorage(
  userId: string | null,
  layers: readonly LayerId[],
): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  try {
    ls.setItem(storageKeyForUser(userId), JSON.stringify(layers));
  } catch {
    // Quota / private mode — best-effort; no user-visible error.
  }
}

// ---------------------------------------------------------------------------
// Hook: hydrate layers from localStorage on mount
// ---------------------------------------------------------------------------

/**
 * Hydrates layers from localStorage once on mount, unless the URL already
 * carries an explicit `layers=` param (URL wins per Req 4.9 + Req 3.10).
 *
 * Emits `onHydrate(layers)` synchronously after mount if a stored value
 * differs from `currentLayers`. On every subsequent change of the returned
 * `persistLayers` callback, writes the new value to localStorage.
 */
export interface UseLayerPersistenceArgs {
  readonly userId: string | null;
  readonly urlHasExplicitLayers: boolean;
  readonly currentLayers: readonly LayerId[];
  readonly onHydrate: (next: readonly LayerId[]) => void;
}

export interface UseLayerPersistenceReturn {
  readonly persistLayers: (layers: readonly LayerId[]) => void;
}

export function useLayerPersistence({
  userId,
  urlHasExplicitLayers,
  currentLayers,
  onHydrate,
}: UseLayerPersistenceArgs): UseLayerPersistenceReturn {
  const hydratedRef = useRef(false);

  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    if (urlHasExplicitLayers) return;
    const stored = readLayersFromStorage(userId);
    if (stored === null) return;
    // Only fire if different from current — avoids needless re-renders.
    if (stored.length === currentLayers.length) {
      let same = true;
      for (let i = 0; i < stored.length; i++) {
        if (stored[i] !== currentLayers[i]) {
          same = false;
          break;
        }
      }
      if (same) return;
    }
    onHydrate(stored);
    // Intentionally depend only on userId: this hook runs once per user.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  const persistLayers = useCallback(
    (layers: readonly LayerId[]) => {
      writeLayersToStorage(userId, layers);
    },
    [userId],
  );

  return { persistLayers };
}

// ---------------------------------------------------------------------------
// Convenience: seed + persist pair for simple consumers
// ---------------------------------------------------------------------------

/**
 * Returns `state` + a setter that also writes layers to localStorage.
 * Kept out of the sidebar itself so the shell can own the authoritative
 * state (it also mirrors layers into the URL via `useJourneyUrlState`).
 */
export function useJourneyFilterState(
  init: JourneyFilterState = initialFilterState(),
): readonly [JourneyFilterState, (next: JourneyFilterState) => void] {
  const [state, setState] = useState<JourneyFilterState>(init);
  return [state, setState] as const;
}
