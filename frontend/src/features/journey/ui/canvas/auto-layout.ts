/**
 * Dagre adapter — computes initial `{x, y}` positions for a flat React Flow
 * node list. Applied once on mount so the canvas loads with a readable
 * left-to-right tree; after that, user drags are authoritative.
 *
 * Covers Req 3.6 — "initial node positions SHALL be computed via `dagre`
 * auto-layout".
 *
 * Dagre centres nodes on their `{x, y}` coordinate; React Flow positions
 * from the top-left corner. We subtract half the node dimensions so the
 * two conventions agree.
 */

import dagre from "@dagrejs/dagre";
import type { Node, Edge } from "@xyflow/react";

const NODE_W = 280;
const NODE_H = 120;

export function computeLayout(
  nodes: readonly Node[],
  edges: readonly Edge[],
): Record<string, { x: number; y: number }> {
  if (nodes.length === 0) return {};

  const g = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", ranksep: 80, nodesep: 40 });

  for (const n of nodes) {
    g.setNode(n.id, { width: NODE_W, height: NODE_H });
  }
  for (const e of edges) {
    // Dagre ignores edges whose endpoints are not set nodes; defensive guard.
    if (g.hasNode(e.source) && g.hasNode(e.target)) {
      g.setEdge(e.source, e.target);
    }
  }

  dagre.layout(g);

  return Object.fromEntries(
    nodes.map((n) => {
      const laid = g.node(n.id);
      const x = (laid?.x ?? 0) - NODE_W / 2;
      const y = (laid?.y ?? 0) - NODE_H / 2;
      return [n.id, { x, y }];
    }),
  );
}
