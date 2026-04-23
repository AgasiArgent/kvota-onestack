/**
 * Snapshot test for the dagre-backed auto-layout. Guards against unintended
 * layout drift during refactors; if dagre output changes (version bump,
 * algorithm tweak), the snapshot will flag it and the engineer can inspect.
 *
 * Covers Req 3.6 — "initial node positions SHALL be computed via `dagre`
 * auto-layout".
 */

import { describe, it, expect } from "vitest";
import type { Node, Edge } from "@xyflow/react";
import { computeLayout } from "../auto-layout";

describe("computeLayout (dagre adapter)", () => {
  it("produces a stable {x,y} map for a fixed 8-node fixture", () => {
    const nodes: Node[] = [
      { id: "app:/quotes", position: { x: 0, y: 0 }, data: {} },
      { id: "app:/quotes/[id]", position: { x: 0, y: 0 }, data: {} },
      { id: "app:/quotes/new", position: { x: 0, y: 0 }, data: {} },
      { id: "app:/procurement", position: { x: 0, y: 0 }, data: {} },
      {
        id: "app:/procurement/suppliers",
        position: { x: 0, y: 0 },
        data: {},
      },
      { id: "app:/logistics", position: { x: 0, y: 0 }, data: {} },
      { id: "ghost:customs-calendar", position: { x: 0, y: 0 }, data: {} },
      { id: "ghost:ai-assistant", position: { x: 0, y: 0 }, data: {} },
    ];
    const edges: Edge[] = [
      { id: "e1", source: "app:/quotes", target: "app:/quotes/[id]" },
      { id: "e2", source: "app:/quotes", target: "app:/quotes/new" },
      {
        id: "e3",
        source: "app:/procurement",
        target: "app:/procurement/suppliers",
      },
    ];

    const layout = computeLayout(nodes, edges);

    // All 8 input ids present in output
    expect(Object.keys(layout).sort()).toEqual(nodes.map((n) => n.id).sort());

    // Numbers are finite (dagre occasionally returns NaN for isolated nodes
    // with mis-typed config — this catches regressions)
    for (const id of Object.keys(layout)) {
      expect(Number.isFinite(layout[id].x)).toBe(true);
      expect(Number.isFinite(layout[id].y)).toBe(true);
    }

    // Snapshot the full mapping. Dagre is deterministic for the same inputs
    // and algorithm version, so this guards against unintended drift.
    expect(layout).toMatchSnapshot();
  });

  it("handles an empty graph without crashing", () => {
    const layout = computeLayout([], []);
    expect(layout).toEqual({});
  });

  it("lays out isolated nodes (no edges) deterministically", () => {
    const nodes: Node[] = [
      { id: "a", position: { x: 0, y: 0 }, data: {} },
      { id: "b", position: { x: 0, y: 0 }, data: {} },
    ];
    const layout = computeLayout(nodes, []);

    expect(Object.keys(layout)).toHaveLength(2);
    expect(Number.isFinite(layout["a"].x)).toBe(true);
    expect(Number.isFinite(layout["b"].x)).toBe(true);
  });
});
