/**
 * Unit tests for the React Flow graph builder used by `<JourneyCanvas />`.
 *
 * The canvas component itself is a thin wrapper around React Flow — the only
 * non-trivial logic is transforming `JourneyNodeAggregated[]` into the
 * `{ nodes, edges }` shape React Flow consumes, including:
 *   - one `clusterSubflow` container per distinct cluster
 *   - each route → `routeNode` child of its cluster
 *   - each ghost → `ghostNode` child of its cluster (or unclustered lane)
 *   - dagre seed positions applied to the flat node list
 *
 * The project does not currently ship `@testing-library/react` or jsdom, and
 * React Flow does not render in a minimal test environment without extensive
 * shims. Existing Task 15 tests follow a pure-function style — we do the same
 * here and exercise `buildReactFlowGraph` directly.
 *
 * Covered requirements:
 *   - Req 3.6 — cluster-level subflows auto-grouped by manifest `cluster`
 *   - Req 3.7 — click-to-open drawer wiring surface (selection flows through
 *     props — tested at the integration layer; here we verify the graph
 *     builder preserves node_id so the click handler can echo it back)
 *   - Req 3.9 — route + ghost nodes appear on the graph
 *   - Req 4.2 — card content fields (title, route, counts, status, badges)
 *     are attached to node `data` so the custom node components can render them
 *   - Req 7.3 — ghost nodes carry `proposed_route` + ghost-status metadata
 */

import { describe, it, expect } from "vitest";
import type { JourneyNodeAggregated } from "@/entities/journey";
import { buildReactFlowGraph } from "../build-graph";

/**
 * 8-node fixture per task brief: a mix of clusters + 2 ghosts.
 *
 * Clusters: "quotes" (3 routes), "procurement" (2 routes), "logistics"
 * (1 route + 1 ghost), and one unclustered ghost (`cluster=""`). Spread
 * deliberately so the grouping logic has to partition.
 */
const FIXTURE: readonly JourneyNodeAggregated[] = [
  {
    node_id: "app:/quotes",
    route: "/quotes",
    title: "Quotes List",
    cluster: "quotes",
    roles: ["sales", "admin"],
    impl_status: "done",
    qa_status: "verified",
    version: 1,
    stories_count: 3,
    feedback_count: 2,
    pins_count: 1,
    ghost_status: null,
    proposed_route: null,
    updated_at: "2026-04-01T00:00:00Z",
  },
  {
    node_id: "app:/quotes/[id]",
    route: "/quotes/[id]",
    title: "Quote Detail",
    cluster: "quotes",
    roles: ["sales"],
    impl_status: "partial",
    qa_status: "untested",
    version: 2,
    stories_count: 5,
    feedback_count: 0,
    pins_count: 0,
    ghost_status: null,
    proposed_route: null,
    updated_at: null,
  },
  {
    node_id: "app:/quotes/new",
    route: "/quotes/new",
    title: "New Quote",
    cluster: "quotes",
    roles: ["sales"],
    impl_status: "missing",
    qa_status: "broken",
    version: 1,
    stories_count: 1,
    feedback_count: 0,
    pins_count: 0,
    ghost_status: null,
    proposed_route: null,
    updated_at: null,
  },
  {
    node_id: "app:/procurement",
    route: "/procurement",
    title: "Procurement",
    cluster: "procurement",
    roles: ["procurement"],
    impl_status: "done",
    qa_status: "untested",
    version: 1,
    stories_count: 2,
    feedback_count: 1,
    pins_count: 0,
    ghost_status: null,
    proposed_route: null,
    updated_at: null,
  },
  {
    node_id: "app:/procurement/suppliers",
    route: "/procurement/suppliers",
    title: "Suppliers",
    cluster: "procurement",
    roles: ["procurement", "admin"],
    impl_status: null,
    qa_status: null,
    version: 0,
    stories_count: 0,
    feedback_count: 0,
    pins_count: 0,
    ghost_status: null,
    proposed_route: null,
    updated_at: null,
  },
  {
    node_id: "app:/logistics",
    route: "/logistics",
    title: "Logistics",
    cluster: "logistics",
    roles: ["logistics"],
    impl_status: "done",
    qa_status: "verified",
    version: 1,
    stories_count: 4,
    feedback_count: 3,
    pins_count: 2,
    ghost_status: null,
    proposed_route: null,
    updated_at: null,
  },
  {
    node_id: "ghost:customs-calendar",
    route: "",
    title: "Customs Calendar (planned)",
    cluster: "logistics",
    roles: ["customs"],
    impl_status: null,
    qa_status: null,
    version: 0,
    stories_count: 0,
    feedback_count: 0,
    pins_count: 0,
    ghost_status: "proposed",
    proposed_route: "/logistics/customs-calendar",
    updated_at: null,
  },
  {
    node_id: "ghost:ai-assistant",
    route: "",
    title: "AI Assistant (planned)",
    cluster: "",
    roles: ["admin"],
    impl_status: null,
    qa_status: null,
    version: 0,
    stories_count: 0,
    feedback_count: 0,
    pins_count: 0,
    ghost_status: "approved",
    proposed_route: "/ai",
    updated_at: null,
  },
];

describe("buildReactFlowGraph", () => {
  it("returns a node per journey-node plus one subflow per distinct cluster", () => {
    const { rfNodes } = buildReactFlowGraph(FIXTURE, []);

    const leafNodes = rfNodes.filter(
      (n) => n.type === "routeNode" || n.type === "ghostNode",
    );
    const subflows = rfNodes.filter((n) => n.type === "clusterSubflow");

    // 6 app routes + 2 ghosts = 8 leaf nodes
    expect(leafNodes).toHaveLength(8);

    // Distinct clusters in fixture: "quotes", "procurement", "logistics", "" (unclustered)
    expect(subflows).toHaveLength(4);
    expect(new Set(subflows.map((n) => n.id))).toEqual(
      new Set([
        "cluster:quotes",
        "cluster:procurement",
        "cluster:logistics",
        "cluster:__unclustered__",
      ]),
    );
  });

  it("assigns each leaf node to its cluster subflow via parentId (Req 3.6)", () => {
    const { rfNodes } = buildReactFlowGraph(FIXTURE, []);
    const byId = new Map(rfNodes.map((n) => [n.id, n]));

    expect(byId.get("app:/quotes")?.parentId).toBe("cluster:quotes");
    expect(byId.get("app:/quotes/[id]")?.parentId).toBe("cluster:quotes");
    expect(byId.get("app:/procurement")?.parentId).toBe("cluster:procurement");
    expect(byId.get("app:/logistics")?.parentId).toBe("cluster:logistics");
    expect(byId.get("ghost:customs-calendar")?.parentId).toBe(
      "cluster:logistics",
    );
    expect(byId.get("ghost:ai-assistant")?.parentId).toBe(
      "cluster:__unclustered__",
    );
  });

  it("tags routes as `routeNode` and ghosts as `ghostNode` (Req 3.9, 7.3)", () => {
    const { rfNodes } = buildReactFlowGraph(FIXTURE, []);
    const byId = new Map(rfNodes.map((n) => [n.id, n]));

    expect(byId.get("app:/quotes")?.type).toBe("routeNode");
    expect(byId.get("app:/procurement")?.type).toBe("routeNode");
    expect(byId.get("ghost:customs-calendar")?.type).toBe("ghostNode");
    expect(byId.get("ghost:ai-assistant")?.type).toBe("ghostNode");
  });

  it("attaches card content fields on node data for the custom renderers (Req 4.2)", () => {
    const { rfNodes } = buildReactFlowGraph(FIXTURE, []);
    const routeNode = rfNodes.find((n) => n.id === "app:/quotes");
    expect(routeNode).toBeDefined();
    const data = routeNode!.data as Record<string, unknown>;

    expect(data.title).toBe("Quotes List");
    expect(data.route).toBe("/quotes");
    expect(data.impl_status).toBe("done");
    expect(data.qa_status).toBe("verified");
    expect(data.stories_count).toBe(3);
    expect(data.pins_count).toBe(1);
    expect(data.feedback_count).toBe(2);
  });

  it("propagates ghost-specific fields on ghost node data (Req 7.3)", () => {
    const { rfNodes } = buildReactFlowGraph(FIXTURE, []);
    const ghost = rfNodes.find((n) => n.id === "ghost:customs-calendar");
    expect(ghost).toBeDefined();
    const data = ghost!.data as Record<string, unknown>;

    expect(data.proposed_route).toBe("/logistics/customs-calendar");
    expect(data.ghost_status).toBe("proposed");
    expect(data.title).toBe("Customs Calendar (planned)");
  });

  it("passes through edges unchanged", () => {
    const edges = [
      { id: "e1", source: "app:/quotes", target: "app:/quotes/[id]" },
      { id: "e2", source: "app:/quotes", target: "app:/quotes/new" },
    ];
    const { rfEdges } = buildReactFlowGraph(FIXTURE, edges);
    expect(rfEdges).toHaveLength(2);
    expect(rfEdges[0].source).toBe("app:/quotes");
  });

  it("produces an empty edges array when none are supplied", () => {
    const { rfEdges } = buildReactFlowGraph(FIXTURE, []);
    expect(rfEdges).toEqual([]);
  });

  it("marks ghost nodes with `isGhost: true` on data for styling hooks", () => {
    const { rfNodes } = buildReactFlowGraph(FIXTURE, []);
    const ghost = rfNodes.find((n) => n.id === "ghost:ai-assistant");
    expect(ghost).toBeDefined();
    expect((ghost!.data as Record<string, unknown>).isGhost).toBe(true);

    const route = rfNodes.find((n) => n.id === "app:/quotes");
    expect((route!.data as Record<string, unknown>).isGhost).toBe(false);
  });
});
