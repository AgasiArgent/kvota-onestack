"use client";

/**
 * React Flow host for the Journey Map canvas.
 *
 * Responsibilities:
 *   - Transform `JourneyNodeAggregated[]` → React Flow `{ nodes, edges }`
 *     via `buildReactFlowGraph` (Req 3.6, 3.9).
 *   - Seed initial positions via dagre (Req 3.6).
 *   - Register the three custom node types (route, ghost, cluster).
 *   - Wire canvas selection to `onSelectNode` so the parent can open/close
 *     the drawer (Req 3.7).
 *   - Provide pan, zoom, minimap, background (Req 3.9).
 *
 * Positions are computed once per `(nodes, edges)` identity so user drags
 * are not overwritten on every render. Persisting drags is a later task.
 */

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeMouseHandler,
  type NodeTypes,
  type OnSelectionChangeFunc,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo } from "react";

import type { JourneyNodeAggregated } from "@/entities/journey";
import { computeLayout } from "./auto-layout";
import { buildReactFlowGraph } from "./build-graph";
import { ClusterSubflow } from "./cluster-subflow";
import { GhostNode } from "./ghost-node";
import { RouteNode } from "./route-node";

const NODE_TYPES: NodeTypes = {
  routeNode: RouteNode,
  ghostNode: GhostNode,
  clusterSubflow: ClusterSubflow,
};

interface JourneyCanvasProps {
  readonly nodes: readonly JourneyNodeAggregated[];
  readonly edges: readonly Edge[];
  readonly selectedNodeId: string | null;
  readonly onSelectNode: (id: string | null) => void;
}

function JourneyCanvasInner({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
}: JourneyCanvasProps) {
  // Build the React Flow graph and seed positions via dagre. The result is
  // memoised on `(nodes, edges)` identity — subsequent user drags live in
  // React Flow's internal state and are not overwritten.
  const initial = useMemo(() => {
    const { rfNodes, rfEdges } = buildReactFlowGraph(nodes, edges);
    const leafNodes = rfNodes.filter((n) => n.type !== "clusterSubflow");
    const layout = computeLayout(leafNodes, rfEdges);
    const positioned: Node[] = rfNodes.map((n) => {
      if (n.type === "clusterSubflow") return n;
      const p = layout[n.id];
      return p ? { ...n, position: p } : n;
    });
    return { nodes: positioned, edges: rfEdges };
  }, [nodes, edges]);

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState(initial.nodes);
  const [rfEdges, , onEdgesChange] = useEdgesState(initial.edges);

  // If the upstream `nodes`/`edges` prop changes (e.g. refetch), push the
  // new layout into React Flow state. Without this, React Flow's hook
  // would latch onto the first render's value and ignore later updates.
  useEffect(() => {
    setRfNodes(initial.nodes);
    // Intentionally omit `setRfNodes` from deps — it's stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial.nodes]);

  const handleNodeClick: NodeMouseHandler = (_evt, node) => {
    // Cluster subflows are non-interactive; clicks on them open nothing.
    if (node.type === "clusterSubflow") return;
    onSelectNode(node.id);
  };

  const handleSelectionChange: OnSelectionChangeFunc = ({
    nodes: selNodes,
  }) => {
    // A deselection (click on empty canvas) fires with `selNodes` empty.
    if (selNodes.length === 0 && selectedNodeId !== null) {
      onSelectNode(null);
    }
  };

  return (
    <ReactFlow
      nodes={rfNodes}
      edges={rfEdges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onNodeClick={handleNodeClick}
      onSelectionChange={handleSelectionChange}
      nodeTypes={NODE_TYPES}
      fitView
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={16} />
      <Controls showInteractive={false} />
      <MiniMap pannable zoomable />
    </ReactFlow>
  );
}

export function JourneyCanvas(props: JourneyCanvasProps) {
  // React Flow requires a Provider for hooks + store access. Wrapping here
  // keeps the outer shell free of the dependency.
  return (
    <ReactFlowProvider>
      <JourneyCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
