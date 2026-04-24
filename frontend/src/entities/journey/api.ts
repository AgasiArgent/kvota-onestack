/**
 * Journey API client — TanStack Query hooks + a minimal fetch wrapper.
 *
 * The Python API (`api/routers/journey.py`) speaks the standard `{success,
 * data}` envelope (Req 16.4). This module:
 *
 *   1. Ships `journeyFetch<T>(path, init?)` — unwraps the envelope, throws on
 *      `success: false`, and keeps the error `code`, `status`, and `data`
 *      payload attached on the thrown Error for callers (stale-version
 *      rollback in particular needs the server-returned current state).
 *   2. Exposes three read hooks (`useNodes`, `useNodeDetail`, `useNodeHistory`)
 *      keyed consistently under `['journey', ...]` so the mutation hook can
 *      invalidate/snapshot with precision.
 *   3. Ships `journeyNodePath(nodeId)` to safely compose the `:path` URL
 *      segment. The backend route is `/api/journey/node/{node_id:path}`,
 *      so slashes inside `app:/quotes/[id]` MUST be preserved — percent-
 *      encoding them breaks the handler.
 *
 * Credentials are included so the Supabase auth cookie reaches the Python
 * API. JWT-bearer auth (for AI agents hitting `/api/*` directly) is handled
 * by `shared/lib/api.ts` — the journey UI runs as the signed-in user, so
 * the cookie path is the right one here.
 */

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listFlows } from "./queries";
import type {
  JourneyFlow,
  JourneyNodeAggregated,
  JourneyNodeDetail,
  JourneyNodeHistoryEntry,
  JourneyNodeId,
} from "./types";

// ---------------------------------------------------------------------------
// Query key constants
// ---------------------------------------------------------------------------

/**
 * Canonical TanStack Query key shape for every journey endpoint. Consumers
 * (mutations, manual invalidations) should import from here to avoid
 * stringly-typed drift between hooks and callers.
 */
export const JOURNEY_QUERY_KEYS = {
  nodes: () => ["journey", "nodes"] as const,
  nodeDetail: (nodeId: JourneyNodeId) => ["journey", "node", nodeId] as const,
  nodeHistory: (nodeId: JourneyNodeId) =>
    ["journey", "node", nodeId, "history"] as const,
  flows: () => ["journey", "flows"] as const,
} as const;

// ---------------------------------------------------------------------------
// Path + fetch helpers
// ---------------------------------------------------------------------------

const NODE_ID_PATTERN = /^(app:|ghost:).+/;

/**
 * Validates and returns the node_id tail exactly as the backend expects it.
 * The backend route is `/api/journey/node/{node_id:path}`; slashes in the
 * tail are part of the path segment and must NOT be percent-encoded.
 *
 * Throws on malformed ids — callers should have a `JourneyNodeId` already
 * (template-literal union) but a runtime guard keeps the JS boundary safe.
 */
export function journeyNodePath(nodeId: JourneyNodeId): string {
  if (typeof nodeId !== "string" || !NODE_ID_PATTERN.test(nodeId)) {
    throw new Error(`Invalid JourneyNodeId: ${String(nodeId)}`);
  }
  return nodeId;
}

/** Error shape thrown by {@link journeyFetch} on non-success envelopes. */
export interface JourneyApiError extends Error {
  readonly code?: string;
  readonly status: number;
  readonly data?: unknown;
}

/**
 * Minimal envelope-aware fetch. On `success: true` → returns `data as T`.
 * On `success: false` → throws an Error with `code`, `status`, and any
 * `data` payload the server returned (used by the mutation hook to snap
 * the client's cache to the server's current state on 409 STALE_VERSION).
 */
export async function journeyFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { ...init, credentials: "include" });
  const body = (await res.json()) as {
    success: boolean;
    data?: T;
    error?: { code?: string; message?: string };
  };

  if (body.success) {
    return body.data as T;
  }

  const err = new Error(body.error?.message ?? "Request failed") as JourneyApiError & {
    code?: string;
    status: number;
    data?: unknown;
  };
  err.code = body.error?.code;
  err.status = res.status;
  err.data = body.data;
  throw err;
}

// ---------------------------------------------------------------------------
// Hooks — read-side (TanStack Query)
// ---------------------------------------------------------------------------

/**
 * Fetch every node on the canvas (manifest + state + counts merged).
 * Maps to `GET /api/journey/nodes` (Task 10).
 */
export function useNodes(): UseQueryResult<JourneyNodeAggregated[]> {
  return useQuery({
    queryKey: JOURNEY_QUERY_KEYS.nodes(),
    queryFn: () => journeyFetch<JourneyNodeAggregated[]>("/api/journey/nodes"),
  });
}

/**
 * Fetch the full drawer payload for a single node.
 * Maps to `GET /api/journey/node/{node_id}` (Task 11).
 */
export function useNodeDetail(nodeId: JourneyNodeId): UseQueryResult<JourneyNodeDetail> {
  return useQuery({
    queryKey: JOURNEY_QUERY_KEYS.nodeDetail(nodeId),
    queryFn: () =>
      journeyFetch<JourneyNodeDetail>(`/api/journey/node/${journeyNodePath(nodeId)}`),
  });
}

/**
 * Fetch the most-recent-50 state-history rows for a node.
 * Maps to `GET /api/journey/node/{node_id}/history` (Task 13).
 */
export function useNodeHistory(
  nodeId: JourneyNodeId
): UseQueryResult<JourneyNodeHistoryEntry[]> {
  return useQuery({
    queryKey: JOURNEY_QUERY_KEYS.nodeHistory(nodeId),
    queryFn: () =>
      journeyFetch<JourneyNodeHistoryEntry[]>(
        `/api/journey/node/${journeyNodePath(nodeId)}/history`
      ),
  });
}

/**
 * Fetch every non-archived curated flow (Req 18.3). Reads Supabase directly
 * via `entities/journey/queries.ts::listFlows` — this is curriculum content
 * guarded by RLS, not business logic, so the API-First rule doesn't require a
 * Python endpoint.
 */
export function useFlows(): UseQueryResult<readonly JourneyFlow[]> {
  return useQuery({
    queryKey: JOURNEY_QUERY_KEYS.flows(),
    queryFn: async () => {
      const { data, error } = await listFlows();
      if (error) throw new Error(error.message);
      return (data ?? []) as readonly JourneyFlow[];
    },
  });
}
