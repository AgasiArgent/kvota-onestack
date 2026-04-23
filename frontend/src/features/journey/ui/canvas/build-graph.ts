/**
 * Pure transformer from the API's `JourneyNodeAggregated[]` list into the
 * `{ nodes, edges }` shape React Flow consumes.
 *
 * Responsibilities (Req 3.6, 3.9, 4.2, 7.3):
 *   - One `clusterSubflow` container per distinct `cluster` field (nodes with
 *     an empty / missing cluster fall into the `__unclustered__` lane).
 *   - Each route (`app:*`) → `routeNode` child of its cluster subflow.
 *   - Each ghost (`ghost:*`) → `ghostNode` child of its cluster subflow.
 *   - All scalar card fields (title, route, status, counts, ghost status,
 *     proposed_route) are attached to `node.data` so the custom node
 *     components render without extra lookups.
 *   - `parentId` wires leaves to their subflow so React Flow's subflow
 *     rendering groups them.
 *   - Edges pass through unchanged — selection/styling belongs to the
 *     caller (Req 3.7 click-to-drawer is wired at the canvas level).
 *
 * Positions are seeded by `auto-layout.ts` in the canvas component after
 * this step; this transformer produces `{ x: 0, y: 0 }` placeholders.
 */

import type { Node, Edge } from "@xyflow/react";
import type {
  GhostStatus,
  ImplStatus,
  JourneyNodeAggregated,
  JourneyNodeId,
  QaStatus,
  RoleSlug,
} from "@/entities/journey";

const UNCLUSTERED_KEY = "__unclustered__";

export interface JourneyNodeCardData {
  readonly node_id: JourneyNodeId;
  readonly title: string;
  readonly route: string;
  readonly cluster: string;
  readonly roles: readonly RoleSlug[];
  readonly impl_status: ImplStatus | null;
  readonly qa_status: QaStatus | null;
  readonly stories_count: number;
  readonly feedback_count: number;
  readonly pins_count: number;
  readonly ghost_status: GhostStatus | null;
  readonly proposed_route: string | null;
  readonly isGhost: boolean;
}

export interface ClusterSubflowData {
  readonly cluster: string;
  readonly label: string;
}

export interface BuildGraphResult {
  readonly rfNodes: Node[];
  readonly rfEdges: Edge[];
}

/**
 * Format a cluster key into a human-readable label. We preserve the raw
 * `cluster` value from the manifest (e.g. "Quotes", "procurement") but
 * substitute a friendly label for the unclustered bucket.
 */
function labelForCluster(cluster: string): string {
  if (cluster === "" || cluster === UNCLUSTERED_KEY) return "Без кластера";
  return cluster;
}

function clusterIdFor(cluster: string): string {
  const key = cluster === "" ? UNCLUSTERED_KEY : cluster;
  return `cluster:${key}`;
}

function isGhostId(nodeId: JourneyNodeId): boolean {
  return nodeId.startsWith("ghost:");
}

export function buildReactFlowGraph(
  nodes: readonly JourneyNodeAggregated[],
  edges: readonly Edge[],
): BuildGraphResult {
  // 1. Collect distinct clusters in insertion order. Using a Map so the
  //    first-seen order is preserved — keeps subflow ordering stable.
  const clusterOrder = new Map<string, string>(); // rawCluster -> label
  for (const n of nodes) {
    const key = n.cluster ?? "";
    if (!clusterOrder.has(key)) {
      clusterOrder.set(key, labelForCluster(key));
    }
  }

  // 2. Emit one subflow container per cluster.
  const subflowNodes: Node[] = Array.from(clusterOrder.entries()).map(
    ([cluster, label]) => ({
      id: clusterIdFor(cluster),
      type: "clusterSubflow",
      position: { x: 0, y: 0 },
      data: { cluster, label } satisfies ClusterSubflowData,
      // React Flow subflows use `style` to set container dimensions;
      // we leave this to the canvas layout pass so dagre-computed child
      // positions can drive container size.
      draggable: false,
      selectable: false,
    }),
  );

  // 3. Emit leaf nodes — one per journey node — parented to its cluster.
  const leafNodes: Node[] = nodes.map((n) => {
    const isGhost = isGhostId(n.node_id);
    const parentId = clusterIdFor(n.cluster ?? "");
    const data: JourneyNodeCardData = {
      node_id: n.node_id,
      title: n.title,
      route: n.route,
      cluster: n.cluster,
      roles: n.roles,
      impl_status: n.impl_status,
      qa_status: n.qa_status,
      stories_count: n.stories_count,
      feedback_count: n.feedback_count,
      pins_count: n.pins_count,
      ghost_status: n.ghost_status,
      proposed_route: n.proposed_route,
      isGhost,
    };
    return {
      id: n.node_id,
      type: isGhost ? "ghostNode" : "routeNode",
      position: { x: 0, y: 0 },
      parentId,
      extent: "parent",
      data: data as unknown as Record<string, unknown>,
    };
  });

  return {
    rfNodes: [...subflowNodes, ...leafNodes],
    rfEdges: edges.map((e) => ({ ...e })),
  };
}
