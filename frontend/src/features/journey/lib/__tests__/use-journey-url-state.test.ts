/**
 * Pure-function tests for the URL-state serialiser/deserialiser used by
 * `useJourneyUrlState`. The React hook itself is thin — it wraps Next.js
 * router primitives; the interesting logic is the encode/decode pair plus
 * the `with*` mutation helpers. We exercise those in isolation.
 *
 * Covered requirements:
 *   - Req 3.10 — URL reflects `node`, `layers`, `viewas`; state restored on load.
 *   - Req 4.1 — Eight layers: roles, stories, impl, qa, feedback, training,
 *     ghost, screenshots (canonical slugs).
 *   - Req 3.4 — `viewas` restricted to the 13 active role slugs.
 */

import { describe, it, expect } from "vitest";
import {
  decodeFromSearchParams,
  encodeToSearchParams,
  withNode,
  withLayers,
  withViewAs,
  ALL_LAYER_IDS,
  DEFAULT_LAYERS,
  type JourneyUrlState,
  type LayerId,
} from "../use-journey-url-state";

const EMPTY_STATE: JourneyUrlState = {
  node: null,
  layers: DEFAULT_LAYERS,
  viewAs: null,
};

describe("ALL_LAYER_IDS — canonical 8 layers from Req 4.1", () => {
  it("contains exactly the eight slugs in requirements order", () => {
    expect(ALL_LAYER_IDS).toEqual([
      "roles",
      "stories",
      "impl",
      "qa",
      "feedback",
      "training",
      "ghost",
      "screenshots",
    ]);
  });
});

describe("decodeFromSearchParams", () => {
  it("returns defaults for an empty URLSearchParams", () => {
    const state = decodeFromSearchParams(new URLSearchParams());
    expect(state).toEqual(EMPTY_STATE);
  });

  it("parses node with the app: prefix untouched", () => {
    const params = new URLSearchParams("node=app:/quotes");
    const state = decodeFromSearchParams(params);
    expect(state.node).toBe("app:/quotes");
  });

  it("parses node with the ghost: prefix", () => {
    const params = new URLSearchParams("node=ghost:planned-page");
    expect(decodeFromSearchParams(params).node).toBe("ghost:planned-page");
  });

  it("rejects node values without app:/ghost: prefix", () => {
    const params = new URLSearchParams("node=invalid-id");
    expect(decodeFromSearchParams(params).node).toBeNull();
  });

  it("parses comma-joined layers in order, filtering unknown slugs", () => {
    const params = new URLSearchParams("layers=impl,qa,bogus,feedback");
    const state = decodeFromSearchParams(params);
    expect(state.layers).toEqual(["impl", "qa", "feedback"]);
  });

  it("treats empty layers= as explicit empty array (no defaults applied)", () => {
    const params = new URLSearchParams("layers=");
    const state = decodeFromSearchParams(params);
    expect(state.layers).toEqual([]);
  });

  it("is case-sensitive on layer slugs", () => {
    const params = new URLSearchParams("layers=IMPL,QA");
    expect(decodeFromSearchParams(params).layers).toEqual([]);
  });

  it("parses viewas when it matches a known RoleSlug", () => {
    const params = new URLSearchParams("viewas=sales");
    expect(decodeFromSearchParams(params).viewAs).toBe("sales");
  });

  it("returns null viewAs for unknown role slugs", () => {
    const params = new URLSearchParams("viewas=marketing");
    expect(decodeFromSearchParams(params).viewAs).toBeNull();
  });

  it("returns null viewAs for legacy role slugs removed in migration 168", () => {
    const params = new URLSearchParams("viewas=sales_manager");
    expect(decodeFromSearchParams(params).viewAs).toBeNull();
  });

  it("handles the full example URL from the Task 15 brief", () => {
    const params = new URLSearchParams(
      "node=app:/quotes&layers=impl,qa&viewas=sales",
    );
    const state = decodeFromSearchParams(params);
    expect(state).toEqual({
      node: "app:/quotes",
      layers: ["impl", "qa"],
      viewAs: "sales",
    });
  });
});

describe("encodeToSearchParams", () => {
  it("omits all params when state is the default", () => {
    const params = encodeToSearchParams(EMPTY_STATE);
    expect(params.toString()).toBe("");
  });

  it("omits node when null", () => {
    const params = encodeToSearchParams({
      node: null,
      layers: DEFAULT_LAYERS,
      viewAs: null,
    });
    expect(params.has("node")).toBe(false);
  });

  it("omits viewas when null", () => {
    const params = encodeToSearchParams({
      node: "app:/quotes",
      layers: DEFAULT_LAYERS,
      viewAs: null,
    });
    expect(params.has("viewas")).toBe(false);
  });

  it("emits layers as comma-joined in the provided order", () => {
    const params = encodeToSearchParams({
      node: null,
      layers: ["qa", "impl"],
      viewAs: null,
    });
    expect(params.get("layers")).toBe("qa,impl");
  });

  it("omits layers when the layers list equals DEFAULT_LAYERS exactly", () => {
    const params = encodeToSearchParams({
      node: null,
      layers: DEFAULT_LAYERS,
      viewAs: null,
    });
    expect(params.has("layers")).toBe(false);
  });

  it("emits layers= (empty) when explicitly empty (differs from default)", () => {
    const params = encodeToSearchParams({
      node: null,
      layers: [],
      viewAs: null,
    });
    expect(params.get("layers")).toBe("");
  });

  it("encodes the full Task 15 example state losslessly", () => {
    const params = encodeToSearchParams({
      node: "app:/quotes",
      layers: ["impl", "qa"],
      viewAs: "sales",
    });
    const decoded = decodeFromSearchParams(params);
    expect(decoded).toEqual({
      node: "app:/quotes",
      layers: ["impl", "qa"],
      viewAs: "sales",
    });
  });
});

describe("round-trip symmetry", () => {
  const cases: JourneyUrlState[] = [
    EMPTY_STATE,
    { node: "app:/quotes", layers: DEFAULT_LAYERS, viewAs: null },
    { node: null, layers: ["impl"], viewAs: "admin" },
    { node: "ghost:planned", layers: [], viewAs: "top_manager" },
    {
      node: "app:/procurement/kanban",
      layers: ["roles", "stories", "ghost"] as readonly LayerId[],
      viewAs: "procurement",
    },
  ];

  it.each(cases)("encode→decode preserves state: %o", (state) => {
    const encoded = encodeToSearchParams(state);
    const decoded = decodeFromSearchParams(encoded);
    expect(decoded).toEqual(state);
  });
});

describe("mutation helpers return new objects", () => {
  it("withNode does not mutate the input", () => {
    const input: JourneyUrlState = {
      node: null,
      layers: DEFAULT_LAYERS,
      viewAs: null,
    };
    const next = withNode(input, "app:/quotes");
    expect(next.node).toBe("app:/quotes");
    expect(input.node).toBeNull();
    expect(next).not.toBe(input);
  });

  it("withNode(null) clears the node", () => {
    const input: JourneyUrlState = {
      node: "app:/quotes",
      layers: DEFAULT_LAYERS,
      viewAs: null,
    };
    expect(withNode(input, null).node).toBeNull();
  });

  it("withLayers replaces the layers array", () => {
    const next = withLayers(EMPTY_STATE, ["qa", "ghost"]);
    expect(next.layers).toEqual(["qa", "ghost"]);
    expect(EMPTY_STATE.layers).toEqual(DEFAULT_LAYERS);
  });

  it("withViewAs updates the role", () => {
    const next = withViewAs(EMPTY_STATE, "finance");
    expect(next.viewAs).toBe("finance");
    expect(EMPTY_STATE.viewAs).toBeNull();
  });

  it("withViewAs(null) clears the role", () => {
    const base: JourneyUrlState = {
      node: null,
      layers: DEFAULT_LAYERS,
      viewAs: "sales",
    };
    expect(withViewAs(base, null).viewAs).toBeNull();
  });
});
