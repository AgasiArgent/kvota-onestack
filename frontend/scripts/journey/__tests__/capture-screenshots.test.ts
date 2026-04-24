/**
 * Unit coverage for the pure helpers behind the journey capture script.
 * Playwright + Supabase I/O is exercised only in CI (via the nightly action)
 * so this file intentionally avoids any dynamic import of the script itself.
 *
 * Task 26 — Requirements §10.2, §10.5, §10.6, §10.8, §10.9.
 */
import { describe, it, expect } from "vitest";

import {
  buildBboxUpdate,
  buildScreenshotPath,
  dryRunSummary,
  listRolesFromManifest,
  nodesForRole,
  nodeIdToSafeSegment,
  pruneRetainedFiles,
  requireEnv,
  substituteDynamicRoute,
} from "../_capture-helpers";

const VIEWPORT = { width: 1280, height: 720 } as const;

describe("requireEnv", () => {
  const full = {
    SUPABASE_URL: "https://example.supabase.co",
    SUPABASE_SERVICE_ROLE_KEY: "sk",
    JOURNEY_WEBHOOK_TOKEN: "wh",
    JOURNEY_BASE_URL: "https://example.com",
    JOURNEY_TEST_USERS_PASSWORD: "pw",
  };

  it("returns a typed env object when every key is present", () => {
    expect(requireEnv(full).JOURNEY_BASE_URL).toBe("https://example.com");
  });

  it("throws listing every missing key", () => {
    expect(() =>
      requireEnv({
        SUPABASE_URL: "x",
        SUPABASE_SERVICE_ROLE_KEY: "",
      }),
    ).toThrow(
      /Missing required env vars: SUPABASE_SERVICE_ROLE_KEY, JOURNEY_WEBHOOK_TOKEN, JOURNEY_BASE_URL, JOURNEY_TEST_USERS_PASSWORD/,
    );
  });
});

describe("nodeIdToSafeSegment", () => {
  it("strips the app: prefix and collapses slashes to underscores", () => {
    expect(nodeIdToSafeSegment("app:/quotes/[id]")).toBe("quotes_id");
  });

  it("handles root node", () => {
    expect(nodeIdToSafeSegment("app:/")).toBe("");
  });

  it("idempotent when already safe", () => {
    expect(nodeIdToSafeSegment("customers")).toBe("customers");
  });
});

describe("buildScreenshotPath", () => {
  it("produces {role}/{node_safe}/{date}.png", () => {
    expect(buildScreenshotPath("sales", "app:/quotes/[id]", "2026-04-23")).toBe(
      "sales/quotes_id/2026-04-23.png",
    );
  });

  it("rejects malformed dates", () => {
    expect(() => buildScreenshotPath("sales", "app:/quotes", "04/23/2026")).toThrow(
      /YYYY-MM-DD/,
    );
  });
});

describe("buildBboxUpdate", () => {
  it("converts a pixel bbox into relative fractions", () => {
    const res = buildBboxUpdate(
      "pin-1",
      { x: 400, y: 200, width: 120, height: 40 },
      VIEWPORT,
    );
    expect(res.pin_id).toBe("pin-1");
    expect(res.bbox).not.toBeNull();
    const { bbox } = res;
    if (!bbox) throw new Error("expected bbox");
    expect(bbox.rel_x).toBeCloseTo(400 / 1280, 10);
    expect(bbox.rel_y).toBeCloseTo(200 / 720, 10);
    expect(bbox.rel_width).toBeCloseTo(120 / 1280, 10);
    expect(bbox.rel_height).toBeCloseTo(40 / 720, 10);
  });

  it("returns bbox:null when Playwright reported no bounding box", () => {
    expect(buildBboxUpdate("pin-2", null, VIEWPORT)).toEqual({
      pin_id: "pin-2",
      bbox: null,
    });
  });

  it("rejects a non-positive viewport", () => {
    expect(() =>
      buildBboxUpdate("pin-3", { x: 0, y: 0, width: 10, height: 10 }, {
        width: 0,
        height: 720,
      }),
    ).toThrow(/positive dimensions/);
  });
});

describe("substituteDynamicRoute", () => {
  const fixtures = {
    "app:/quotes/[id]": "abc-123",
    "app:/customers/[id]": "cust-uuid",
  };

  it("returns static routes untouched", () => {
    expect(substituteDynamicRoute("app:/quotes", "/quotes", fixtures)).toBe("/quotes");
  });

  it("substitutes a single [id] placeholder", () => {
    expect(
      substituteDynamicRoute("app:/quotes/[id]", "/quotes/[id]", fixtures),
    ).toBe("/quotes/abc-123");
  });

  it("returns null when the fixture is missing", () => {
    expect(
      substituteDynamicRoute("app:/deals/[id]", "/deals/[id]", fixtures),
    ).toBeNull();
  });

  it("returns null when the fixture is empty string", () => {
    expect(
      substituteDynamicRoute("app:/x/[id]", "/x/[id]", { "app:/x/[id]": "" }),
    ).toBeNull();
  });
});

describe("pruneRetainedFiles", () => {
  it("keeps the 2 newest, returns the rest", () => {
    const files = [
      { path: "a/b/2026-04-20.png", date: "2026-04-20" },
      { path: "a/b/2026-04-22.png", date: "2026-04-22" },
      { path: "a/b/2026-04-23.png", date: "2026-04-23" },
      { path: "a/b/2026-04-18.png", date: "2026-04-18" },
      { path: "a/b/2026-04-15.png", date: "2026-04-15" },
    ];
    const toDelete = pruneRetainedFiles(files, 2);
    expect(toDelete).toEqual([
      "a/b/2026-04-20.png",
      "a/b/2026-04-18.png",
      "a/b/2026-04-15.png",
    ]);
  });

  it("returns [] when already under the retention cap", () => {
    expect(
      pruneRetainedFiles(
        [{ path: "x.png", date: "2026-04-23" }],
        2,
      ),
    ).toEqual([]);
  });

  it("rejects negative keep", () => {
    expect(() => pruneRetainedFiles([], -1)).toThrow(/keep must be >=0/);
  });
});

describe("dryRunSummary", () => {
  it("produces a stable multi-line summary", () => {
    expect(
      dryRunSummary({
        roles: ["sales", "admin"],
        nodesVisited: 42,
        pinsResolved: 15,
        pinsBroken: 2,
      }),
    ).toMatchInlineSnapshot(`
      "[journey-capture] dry-run summary
        roles: admin, sales
        nodes visited: 42
        pins resolved: 15
        pins broken:   2"
    `);
  });
});

describe("listRolesFromManifest / nodesForRole", () => {
  const manifest = {
    nodes: [
      { node_id: "app:/a", route: "/a", roles: ["sales", "admin"] },
      { node_id: "app:/b", route: "/b", roles: [] },
      { node_id: "app:/c", route: "/c", roles: ["procurement"] },
      { node_id: "app:/d", route: "/d", roles: ["sales"] },
    ],
  };

  it("deduplicates and sorts roles", () => {
    expect(listRolesFromManifest(manifest)).toEqual([
      "admin",
      "procurement",
      "sales",
    ]);
  });

  it("filters nodes visible to a role", () => {
    expect(nodesForRole(manifest, "sales").map((n) => n.node_id)).toEqual([
      "app:/a",
      "app:/d",
    ]);
  });
});
