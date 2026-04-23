/**
 * Optimistic mutation hook for `PATCH /api/journey/node/{node_id}/state`.
 *
 * Flow (aligned with Req 6 of customer-journey-map spec):
 *
 *   onMutate   → snapshot current cache entry via `getQueryData`, apply
 *                the patch optimistically so the drawer reflects the new
 *                state immediately.
 *   onError    → rollback strategy depends on error code:
 *                  • STALE_VERSION (HTTP 409): the server returned the
 *                    authoritative current state in `error.data.current`.
 *                    Seed the cache with it so the UI shows fresh values,
 *                    then re-throw so the component renders a conflict
 *                    banner with a refresh CTA (Req 6.2).
 *                  • FORBIDDEN_FIELD (HTTP 403) / any other: rollback to
 *                    the snapshot and re-throw so the component surfaces
 *                    a toast (Req 6.4–6.6).
 *   onSuccess  → invalidate the canvas aggregate list so counts / dots
 *                refresh. The node-detail cache is already updated with
 *                the authoritative row returned by the server.
 */

import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";
import { JOURNEY_QUERY_KEYS, journeyFetch, journeyNodePath } from "./api";
import type {
  ImplStatus,
  JourneyNodeDetail,
  JourneyNodeId,
  QaStatus,
} from "./types";

/** Body of a state PATCH as sent to the Python API. */
export interface JourneyStatePatch {
  readonly version: number;
  readonly impl_status?: ImplStatus | null;
  readonly qa_status?: QaStatus | null;
  readonly notes?: string | null;
}

interface MutationVars {
  readonly nodeId: JourneyNodeId;
  readonly patch: JourneyStatePatch;
}

interface MutationContext {
  readonly nodeId: JourneyNodeId;
  readonly previous: JourneyNodeDetail | undefined;
}

type ThrownError = Error & {
  code?: string;
  status?: number;
  data?: { current?: JourneyNodeDetail } | unknown;
};

/**
 * Build the optimistic detail payload by applying the patch on top of the
 * cached row. Keeps `readonly` shapes intact — we create a new object
 * rather than mutating in place.
 */
function applyPatch(
  previous: JourneyNodeDetail,
  patch: JourneyStatePatch
): JourneyNodeDetail {
  return {
    ...previous,
    impl_status: patch.impl_status !== undefined ? patch.impl_status : previous.impl_status,
    qa_status: patch.qa_status !== undefined ? patch.qa_status : previous.qa_status,
    notes: patch.notes !== undefined ? patch.notes : previous.notes,
    // version is bumped server-side; we leave it as-is optimistically so
    // the next PATCH still sends the old version if the user chains edits.
  };
}

/**
 * Mutation hook: PATCH node state with optimistic concurrency.
 * Returns a typical `UseMutationResult`; components call `.mutateAsync()`
 * and catch thrown errors to render conflict or permission toasts.
 */
export function useUpdateNodeState(): UseMutationResult<
  JourneyNodeDetail,
  ThrownError,
  MutationVars,
  MutationContext
> {
  const queryClient = useQueryClient();

  return useMutation<JourneyNodeDetail, ThrownError, MutationVars, MutationContext>({
    mutationFn: async ({ nodeId, patch }) => {
      return journeyFetch<JourneyNodeDetail>(
        `/api/journey/node/${journeyNodePath(nodeId)}/state`,
        {
          method: "PATCH",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(patch),
        }
      );
    },

    onMutate: async ({ nodeId, patch }) => {
      const key = JOURNEY_QUERY_KEYS.nodeDetail(nodeId);
      // Cancel any in-flight refetches so they don't clobber the optimistic value.
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<JourneyNodeDetail>(key);
      if (previous) {
        queryClient.setQueryData<JourneyNodeDetail>(key, applyPatch(previous, patch));
      }
      return { nodeId, previous };
    },

    onError: (err, _vars, context) => {
      if (!context) return;
      const key = JOURNEY_QUERY_KEYS.nodeDetail(context.nodeId);
      // STALE_VERSION: seed cache with server's authoritative current state.
      if (
        err.code === "STALE_VERSION" &&
        err.data &&
        typeof err.data === "object" &&
        "current" in (err.data as Record<string, unknown>)
      ) {
        const current = (err.data as { current?: JourneyNodeDetail }).current;
        if (current) {
          queryClient.setQueryData<JourneyNodeDetail>(key, current);
          return;
        }
      }
      // Everything else: rollback to snapshot.
      if (context.previous) {
        queryClient.setQueryData<JourneyNodeDetail>(key, context.previous);
      }
    },

    onSuccess: (fresh, { nodeId }) => {
      const key = JOURNEY_QUERY_KEYS.nodeDetail(nodeId);
      queryClient.setQueryData<JourneyNodeDetail>(key, fresh);
      // Canvas counts / status dots may have moved — refresh the list.
      queryClient.invalidateQueries({ queryKey: JOURNEY_QUERY_KEYS.nodes() });
    },
  });
}
