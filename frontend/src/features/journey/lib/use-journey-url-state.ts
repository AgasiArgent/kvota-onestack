"use client";

/**
 * URL-state hook for the `/journey` page.
 *
 * Mirrors the three query parameters defined in Req 3.10:
 *   - `node`    — selected `JourneyNodeId` (`app:` or `ghost:` prefix required)
 *   - `layers`  — comma-joined list of active layer slugs (Req 4.1)
 *   - `viewas`  — role filter, one of the 13 active `RoleSlug` values
 *
 * The pure encode/decode pair is exported for unit tests and for the Server
 * Component that needs to hydrate initial state from `searchParams`.
 *
 * Router updates use `router.replace` (not `push`) per Req 3.10 — state
 * changes should not pollute browser history.
 */

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";
import type { JourneyNodeId, RoleSlug } from "@/entities/journey";

// ---------------------------------------------------------------------------
// Layer IDs — authoritative list per requirements.md §4.1
// ---------------------------------------------------------------------------

export const ALL_LAYER_IDS = [
  "roles",
  "stories",
  "impl",
  "qa",
  "feedback",
  "training",
  "ghost",
  "screenshots",
] as const;

export type LayerId = (typeof ALL_LAYER_IDS)[number];

/**
 * Default layers shown on first load when no `?layers=` param is present.
 * Chosen to match the developer-gap-analysis scenario from Req 1 (P1 dev team):
 * what exists, who it's for, is it implemented, is it verified.
 */
export const DEFAULT_LAYERS: readonly LayerId[] = [
  "impl",
  "qa",
  "feedback",
  "roles",
];

// ---------------------------------------------------------------------------
// RoleSlug validation (13 active roles per migration 168, 2026-02-11)
// ---------------------------------------------------------------------------

const KNOWN_ROLE_SLUGS: ReadonlySet<RoleSlug> = new Set<RoleSlug>([
  "admin",
  "top_manager",
  "head_of_sales",
  "head_of_procurement",
  "head_of_logistics",
  "sales",
  "quote_controller",
  "spec_controller",
  "finance",
  "procurement",
  "procurement_senior",
  "logistics",
  "customs",
]);

const KNOWN_LAYERS: ReadonlySet<string> = new Set(ALL_LAYER_IDS);

// ---------------------------------------------------------------------------
// State shape
// ---------------------------------------------------------------------------

export interface JourneyUrlState {
  readonly node: JourneyNodeId | null;
  readonly layers: readonly LayerId[];
  readonly viewAs: RoleSlug | null;
}

// ---------------------------------------------------------------------------
// Pure helpers — exported for unit tests and SSR hydration
// ---------------------------------------------------------------------------

function isJourneyNodeId(value: string): value is JourneyNodeId {
  return value.startsWith("app:") || value.startsWith("ghost:");
}

function isRoleSlug(value: string): value is RoleSlug {
  return KNOWN_ROLE_SLUGS.has(value as RoleSlug);
}

function isLayerId(value: string): value is LayerId {
  return KNOWN_LAYERS.has(value);
}

function layersEqual(
  a: readonly LayerId[],
  b: readonly LayerId[],
): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

export function decodeFromSearchParams(
  params: URLSearchParams,
): JourneyUrlState {
  const rawNode = params.get("node");
  const node = rawNode && isJourneyNodeId(rawNode) ? rawNode : null;

  const rawLayers = params.get("layers");
  let layers: readonly LayerId[];
  if (rawLayers === null) {
    layers = DEFAULT_LAYERS;
  } else if (rawLayers === "") {
    layers = [];
  } else {
    layers = rawLayers.split(",").filter(isLayerId);
  }

  const rawViewAs = params.get("viewas");
  const viewAs = rawViewAs && isRoleSlug(rawViewAs) ? rawViewAs : null;

  return { node, layers, viewAs };
}

export function encodeToSearchParams(state: JourneyUrlState): URLSearchParams {
  const params = new URLSearchParams();

  if (state.node !== null) {
    params.set("node", state.node);
  }

  if (!layersEqual(state.layers, DEFAULT_LAYERS)) {
    // `URLSearchParams.set` encodes an empty string correctly — URL will
    // carry `layers=` to distinguish "explicit none" from "use defaults".
    params.set("layers", state.layers.join(","));
  }

  if (state.viewAs !== null) {
    params.set("viewas", state.viewAs);
  }

  return params;
}

// ---------------------------------------------------------------------------
// Mutation helpers (pure)
// ---------------------------------------------------------------------------

export function withNode(
  state: JourneyUrlState,
  node: JourneyNodeId | null,
): JourneyUrlState {
  return { ...state, node };
}

export function withLayers(
  state: JourneyUrlState,
  layers: readonly LayerId[],
): JourneyUrlState {
  return { ...state, layers };
}

export function withViewAs(
  state: JourneyUrlState,
  viewAs: RoleSlug | null,
): JourneyUrlState {
  return { ...state, viewAs };
}

// ---------------------------------------------------------------------------
// React hook
// ---------------------------------------------------------------------------

export interface UseJourneyUrlStateReturn {
  state: JourneyUrlState;
  setNode: (node: JourneyNodeId | null) => void;
  setLayers: (layers: readonly LayerId[]) => void;
  setViewAs: (viewAs: RoleSlug | null) => void;
}

export function useJourneyUrlState(): UseJourneyUrlStateReturn {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const state = useMemo(
    () =>
      decodeFromSearchParams(
        new URLSearchParams(searchParams?.toString() ?? ""),
      ),
    [searchParams],
  );

  const replaceParams = useCallback(
    (next: JourneyUrlState) => {
      const qs = encodeToSearchParams(next).toString();
      const url = qs ? `${pathname}?${qs}` : pathname;
      router.replace(url, { scroll: false });
    },
    [pathname, router],
  );

  const setNode = useCallback(
    (node: JourneyNodeId | null) => replaceParams(withNode(state, node)),
    [replaceParams, state],
  );

  const setLayers = useCallback(
    (layers: readonly LayerId[]) => replaceParams(withLayers(state, layers)),
    [replaceParams, state],
  );

  const setViewAs = useCallback(
    (viewAs: RoleSlug | null) => replaceParams(withViewAs(state, viewAs)),
    [replaceParams, state],
  );

  return { state, setNode, setLayers, setViewAs };
}
