/**
 * Pure-function tests for the journey sidebar filter helpers.
 *
 * Reqs:
 *   - Req 3.3 — sidebar sections order.
 *   - Req 3.4 — viewAs = role ⇒ only nodes where that role is listed remain.
 *   - Req 3.5 — search matches route/title/story text case-insensitively,
 *     non-matches fade (returned in `fadedIds`, still present on canvas).
 *   - Req 4.1 — eight canonical layers.
 *   - Req 4.9 — layers persisted in localStorage keyed per user; URL overrides.
 *   - Req 4.10 — status filters applied (impl/qa).
 *
 * No DOM is available in the project's vitest config — we unit-test the
 * pure state transitions and the filter helper. Component-level interactive
 * behaviour is covered by localhost browser verification.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  applyJourneyFilters,
  initialFilterState,
  toggleLayer,
  toggleExclusion,
  readLayersFromStorage,
  writeLayersToStorage,
  storageKeyForUser,
  type JourneyFilterState,
} from "../use-journey-filter";
import type {
  JourneyNodeAggregated,
  JourneyNodeId,
  RoleSlug,
} from "@/entities/journey";
import { ALL_LAYER_IDS, DEFAULT_LAYERS } from "../use-journey-url-state";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeNode(
  id: string,
  overrides: Partial<JourneyNodeAggregated> = {},
): JourneyNodeAggregated {
  const node_id = (
    id.startsWith("app:") || id.startsWith("ghost:") ? id : `app:${id}`
  ) as JourneyNodeId;
  return {
    node_id,
    route: overrides.route ?? `/${id.replace("app:", "").replace("ghost:", "")}`,
    title: overrides.title ?? id,
    cluster: overrides.cluster ?? "misc",
    roles: overrides.roles ?? (["admin"] as const),
    impl_status: overrides.impl_status ?? null,
    qa_status: overrides.qa_status ?? null,
    version: overrides.version ?? 0,
    stories_count: overrides.stories_count ?? 0,
    feedback_count: overrides.feedback_count ?? 0,
    pins_count: overrides.pins_count ?? 0,
    ghost_status: overrides.ghost_status ?? null,
    proposed_route: overrides.proposed_route ?? null,
    updated_at: overrides.updated_at ?? null,
  };
}

const QUOTES_SALES = makeNode("app:/quotes", {
  route: "/quotes",
  title: "Список КП",
  cluster: "quotes",
  roles: ["sales" as RoleSlug, "quote_controller" as RoleSlug],
  impl_status: "done",
  qa_status: "verified",
});

const QUOTES_EDIT = makeNode("app:/quotes/[id]", {
  route: "/quotes/[id]",
  title: "Редактирование КП",
  cluster: "quotes",
  roles: ["sales" as RoleSlug],
  impl_status: "partial",
  qa_status: "untested",
});

const DEALS_FINANCE = makeNode("app:/deals", {
  route: "/deals",
  title: "Сделки",
  cluster: "deals",
  roles: ["finance" as RoleSlug],
  impl_status: "missing",
  qa_status: "broken",
});

const GHOST_PAYMENTS = makeNode("ghost:payments-v2", {
  route: "",
  title: "Платежи v2",
  cluster: "payments",
  roles: ["finance" as RoleSlug],
  impl_status: null,
  qa_status: null,
  ghost_status: "proposed",
  proposed_route: "/payments-v2",
});

const ALL_NODES: readonly JourneyNodeAggregated[] = [
  QUOTES_SALES,
  QUOTES_EDIT,
  DEALS_FINANCE,
  GHOST_PAYMENTS,
];

// ---------------------------------------------------------------------------
// initialFilterState
// ---------------------------------------------------------------------------

describe("initialFilterState", () => {
  it("defaults to DEFAULT_LAYERS, no exclusions, empty search, no viewAs", () => {
    const s = initialFilterState();
    expect(s.layers).toEqual(DEFAULT_LAYERS);
    expect(s.viewAs).toBeNull();
    expect(s.clustersExcluded).toEqual([]);
    expect(s.implStatusesExcluded).toEqual([]);
    expect(s.qaStatusesExcluded).toEqual([]);
    expect(s.search).toBe("");
  });
});

// ---------------------------------------------------------------------------
// toggleLayer — pure layer add/remove
// ---------------------------------------------------------------------------

describe("toggleLayer", () => {
  it("removes layer when present", () => {
    const next = toggleLayer(DEFAULT_LAYERS, "impl");
    expect(next).not.toContain("impl");
    // other defaults preserved
    expect(next).toContain("qa");
  });

  it("adds layer when absent", () => {
    const base = ["qa", "feedback"] as const;
    const next = toggleLayer(base, "impl");
    expect(next).toContain("impl");
    expect(next).toContain("qa");
    expect(next).toContain("feedback");
  });

  it("returns a new array (immutability)", () => {
    const base = [...DEFAULT_LAYERS];
    const next = toggleLayer(base, "impl");
    expect(next).not.toBe(base);
    // original untouched
    expect(base).toEqual(DEFAULT_LAYERS);
  });

  it("preserves canonical order from ALL_LAYER_IDS", () => {
    // toggle off then back on — must land in ALL_LAYER_IDS order.
    const off = toggleLayer(DEFAULT_LAYERS, "impl");
    const on = toggleLayer(off, "impl");
    // relative order of impl vs qa should match ALL_LAYER_IDS
    const implIdx = on.indexOf("impl");
    const qaIdx = on.indexOf("qa");
    const canonicalImpl = ALL_LAYER_IDS.indexOf("impl");
    const canonicalQa = ALL_LAYER_IDS.indexOf("qa");
    expect(implIdx < qaIdx).toBe(canonicalImpl < canonicalQa);
  });
});

// ---------------------------------------------------------------------------
// toggleExclusion — generic exclusion list toggle
// ---------------------------------------------------------------------------

describe("toggleExclusion", () => {
  it("adds value when absent (marking it excluded)", () => {
    const next = toggleExclusion<string>([], "quotes");
    expect(next).toContain("quotes");
  });

  it("removes value when present (re-including it)", () => {
    const next = toggleExclusion<string>(["quotes", "deals"], "quotes");
    expect(next).not.toContain("quotes");
    expect(next).toContain("deals");
  });

  it("returns a new array", () => {
    const base = ["quotes"];
    const next = toggleExclusion<string>(base, "deals");
    expect(next).not.toBe(base);
    expect(base).toEqual(["quotes"]);
  });
});

// ---------------------------------------------------------------------------
// applyJourneyFilters — the core engine (Reqs 3.4, 3.5, 4.10)
// ---------------------------------------------------------------------------

describe("applyJourneyFilters — baseline", () => {
  it("returns everything visible and nothing faded with defaults", () => {
    const { visibleIds, fadedIds } = applyJourneyFilters(ALL_NODES, initialFilterState());
    expect(visibleIds.size).toBe(ALL_NODES.length);
    expect(fadedIds.size).toBe(0);
    for (const n of ALL_NODES) {
      expect(visibleIds.has(n.node_id)).toBe(true);
    }
  });
});

describe("applyJourneyFilters — Req 3.4 viewAs", () => {
  it("filters out nodes whose roles do not include viewAs", () => {
    const state: JourneyFilterState = { ...initialFilterState(), viewAs: "sales" };
    const { visibleIds } = applyJourneyFilters(ALL_NODES, state);
    expect(visibleIds.has(QUOTES_SALES.node_id)).toBe(true);
    expect(visibleIds.has(QUOTES_EDIT.node_id)).toBe(true);
    expect(visibleIds.has(DEALS_FINANCE.node_id)).toBe(false);
    expect(visibleIds.has(GHOST_PAYMENTS.node_id)).toBe(false);
  });

  it("null viewAs = all roles (admin view), no role filtering", () => {
    const state: JourneyFilterState = { ...initialFilterState(), viewAs: null };
    const { visibleIds } = applyJourneyFilters(ALL_NODES, state);
    expect(visibleIds.size).toBe(ALL_NODES.length);
  });
});

describe("applyJourneyFilters — Req 4.10 impl/qa status filters", () => {
  it("excludes nodes with excluded impl_status", () => {
    const state: JourneyFilterState = {
      ...initialFilterState(),
      implStatusesExcluded: ["missing"],
    };
    const { visibleIds } = applyJourneyFilters(ALL_NODES, state);
    expect(visibleIds.has(DEALS_FINANCE.node_id)).toBe(false); // impl=missing
    expect(visibleIds.has(QUOTES_SALES.node_id)).toBe(true); // impl=done
  });

  it("excludes nodes with excluded qa_status", () => {
    const state: JourneyFilterState = {
      ...initialFilterState(),
      qaStatusesExcluded: ["broken"],
    };
    const { visibleIds } = applyJourneyFilters(ALL_NODES, state);
    expect(visibleIds.has(DEALS_FINANCE.node_id)).toBe(false); // qa=broken
    expect(visibleIds.has(QUOTES_SALES.node_id)).toBe(true); // qa=verified
  });

  it("treats null impl_status as 'unset' for exclusion", () => {
    const state: JourneyFilterState = {
      ...initialFilterState(),
      implStatusesExcluded: ["unset"],
    };
    const { visibleIds } = applyJourneyFilters(ALL_NODES, state);
    expect(visibleIds.has(GHOST_PAYMENTS.node_id)).toBe(false); // impl=null
    expect(visibleIds.has(QUOTES_SALES.node_id)).toBe(true);
  });
});

describe("applyJourneyFilters — cluster multi-select", () => {
  it("excludes nodes whose cluster is in clustersExcluded", () => {
    const state: JourneyFilterState = {
      ...initialFilterState(),
      clustersExcluded: ["quotes"],
    };
    const { visibleIds } = applyJourneyFilters(ALL_NODES, state);
    expect(visibleIds.has(QUOTES_SALES.node_id)).toBe(false);
    expect(visibleIds.has(QUOTES_EDIT.node_id)).toBe(false);
    expect(visibleIds.has(DEALS_FINANCE.node_id)).toBe(true);
  });
});

describe("applyJourneyFilters — Req 3.5 search", () => {
  it("matches by route (case-insensitive), non-matches fade but stay visible", () => {
    const state: JourneyFilterState = {
      ...initialFilterState(),
      search: "QUOTES",
    };
    const { visibleIds, fadedIds } = applyJourneyFilters(ALL_NODES, state);
    // All nodes remain on canvas (per Req 3.5)
    expect(visibleIds.size).toBe(ALL_NODES.length);
    // Matches NOT faded
    expect(fadedIds.has(QUOTES_SALES.node_id)).toBe(false);
    expect(fadedIds.has(QUOTES_EDIT.node_id)).toBe(false);
    // Non-matches faded
    expect(fadedIds.has(DEALS_FINANCE.node_id)).toBe(true);
    expect(fadedIds.has(GHOST_PAYMENTS.node_id)).toBe(true);
  });

  it("matches by title (Russian text, case-insensitive)", () => {
    const state: JourneyFilterState = {
      ...initialFilterState(),
      search: "сделки",
    };
    const { fadedIds } = applyJourneyFilters(ALL_NODES, state);
    expect(fadedIds.has(DEALS_FINANCE.node_id)).toBe(false);
    expect(fadedIds.has(QUOTES_SALES.node_id)).toBe(true);
  });

  it("matches by ghost proposed_route", () => {
    const state: JourneyFilterState = {
      ...initialFilterState(),
      search: "payments-v2",
    };
    const { fadedIds } = applyJourneyFilters(ALL_NODES, state);
    expect(fadedIds.has(GHOST_PAYMENTS.node_id)).toBe(false);
  });

  it("empty search = no fading", () => {
    const state: JourneyFilterState = { ...initialFilterState(), search: "" };
    const { fadedIds } = applyJourneyFilters(ALL_NODES, state);
    expect(fadedIds.size).toBe(0);
  });

  it("whitespace-only search = no fading", () => {
    const state: JourneyFilterState = { ...initialFilterState(), search: "   " };
    const { fadedIds } = applyJourneyFilters(ALL_NODES, state);
    expect(fadedIds.size).toBe(0);
  });

  it("hidden nodes (from other filters) never appear in fadedIds", () => {
    const state: JourneyFilterState = {
      ...initialFilterState(),
      viewAs: "sales",
      search: "сделки",
    };
    const { visibleIds, fadedIds } = applyJourneyFilters(ALL_NODES, state);
    // DEALS_FINANCE is hidden by viewAs=sales — must not appear faded either
    expect(visibleIds.has(DEALS_FINANCE.node_id)).toBe(false);
    expect(fadedIds.has(DEALS_FINANCE.node_id)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// localStorage persistence (Req 4.9)
// ---------------------------------------------------------------------------

describe("storageKeyForUser", () => {
  it("uses stable per-user key format", () => {
    expect(storageKeyForUser("user-123")).toBe("journey:layers:user-123");
  });

  it("uses anonymous key when userId is null", () => {
    expect(storageKeyForUser(null)).toBe("journey:layers:anonymous");
  });
});

describe("readLayersFromStorage / writeLayersToStorage", () => {
  // Stub localStorage (not available by default in the no-DOM test env).
  let storage: Record<string, string>;

  beforeEach(() => {
    storage = {};
    vi.stubGlobal("localStorage", {
      getItem: (k: string) => storage[k] ?? null,
      setItem: (k: string, v: string) => {
        storage[k] = v;
      },
      removeItem: (k: string) => {
        delete storage[k];
      },
      clear: () => {
        storage = {};
      },
      key: () => null,
      length: 0,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns null when no value stored", () => {
    expect(readLayersFromStorage("user-1")).toBeNull();
  });

  it("round-trips a layer list", () => {
    writeLayersToStorage("user-1", ["impl", "qa"]);
    expect(readLayersFromStorage("user-1")).toEqual(["impl", "qa"]);
  });

  it("filters out unknown layer slugs when reading (defensive)", () => {
    storage[storageKeyForUser("user-1")] = JSON.stringify([
      "impl",
      "bogus",
      "qa",
    ]);
    expect(readLayersFromStorage("user-1")).toEqual(["impl", "qa"]);
  });

  it("returns null on malformed JSON", () => {
    storage[storageKeyForUser("user-1")] = "not json";
    expect(readLayersFromStorage("user-1")).toBeNull();
  });

  it("returns null when stored value is not an array", () => {
    storage[storageKeyForUser("user-1")] = JSON.stringify({ foo: "bar" });
    expect(readLayersFromStorage("user-1")).toBeNull();
  });

  it("keys are scoped per user (read isolation)", () => {
    writeLayersToStorage("user-1", ["impl"]);
    writeLayersToStorage("user-2", ["qa"]);
    expect(readLayersFromStorage("user-1")).toEqual(["impl"]);
    expect(readLayersFromStorage("user-2")).toEqual(["qa"]);
  });
});

describe("readLayersFromStorage — no localStorage at all", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", undefined);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns null gracefully in SSR-style environments", () => {
    expect(readLayersFromStorage("user-1")).toBeNull();
  });
});
