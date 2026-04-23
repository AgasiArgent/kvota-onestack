"use client";

/**
 * Cluster subflow container — a React Flow "group" node rendered as the
 * parent of all leaf nodes sharing a `cluster` value.
 *
 * Reqs:
 *   - 3.6 — cluster-level subflows auto-grouped by the `cluster` field
 *
 * Visual role: a soft-bordered frame with the cluster label pinned at the
 * top-left so users can tell at a glance which domain a block of nodes
 * belongs to.
 */

import type { NodeProps } from "@xyflow/react";
import type { ClusterSubflowData } from "./build-graph";

export function ClusterSubflow({ data, id }: NodeProps) {
  const d = data as unknown as ClusterSubflowData;

  return (
    <div
      data-testid={`cluster-subflow-${d.cluster || "__unclustered__"}`}
      data-cluster-id={id}
      className="rounded-lg border border-dashed border-border-light bg-accent-subtle/40 h-full w-full"
    >
      <div className="sticky top-0 left-0 px-3 py-1 text-xs font-medium text-text-muted">
        {d.label}
      </div>
    </div>
  );
}
