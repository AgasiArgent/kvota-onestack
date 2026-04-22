/**
 * parse-routes.ts — unit tests (Task 4).
 *
 * Fixtures live under `__tests__/fixtures/routes/` and mimic a realistic
 * Next.js 15 App Router tree so we can cover every route convention without
 * coupling to the real `frontend/src/app/**`.
 */
import path from "node:path";
import { describe, it, expect } from "vitest";

import { parseRoutes, type ParsedRoute } from "../parse-routes";

const FIXTURES_ROOT = path.resolve(__dirname, "fixtures/routes");

/** Small helper: find one route by path, fail loudly if missing. */
function byRoute(routes: readonly ParsedRoute[], route: string): ParsedRoute {
  const found = routes.find((r) => r.route === route);
  if (!found) {
    throw new Error(
      `Expected route '${route}' not found. Got: ${routes
        .map((r) => r.route)
        .join(", ")}`
    );
  }
  return found;
}

describe("parseRoutes", () => {
  it("emits one entry per page.tsx under (app), skips (auth)", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);

    // All six (app) pages present; (auth)/login skipped.
    const paths = routes.map((r) => r.route).sort();
    expect(paths).toEqual(
      [
        "/(.)modal",
        "/dashboard/@feed",
        "/quotes",
        "/quotes/[id]",
        "/quotes/[id]/cost-analysis",
        "/shop/[[...slug]]",
      ].sort()
    );
    expect(paths).not.toContain("/login");
  });

  it("strips (app) and (auth) route groups from the public path", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    for (const r of routes) {
      expect(r.route.includes("(app)")).toBe(false);
      expect(r.route.includes("(auth)")).toBe(false);
    }
  });

  it("preserves [id] dynamic segment brackets in route", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const detail = byRoute(routes, "/quotes/[id]");
    expect(detail.route).toBe("/quotes/[id]");
    expect(detail.node_id).toBe("app:/quotes/[id]");
  });

  it("handles nested dynamic routes (/quotes/[id]/cost-analysis)", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const child = byRoute(routes, "/quotes/[id]/cost-analysis");
    expect(child.title).toBe("Cost Analysis"); // from <h1>
  });

  it("handles optional catch-all [[...slug]] with a flag", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const catchAll = byRoute(routes, "/shop/[[...slug]]");
    expect(catchAll.is_catch_all).toBe(true);
    expect(catchAll.title).toBe("Shop"); // basename fallback
  });

  it("emits a separate entry for parallel routes (@slot)", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const parallel = byRoute(routes, "/dashboard/@feed");
    expect(parallel.is_parallel_slot).toBe(true);
    expect(parallel.parallel_slot).toBe("feed");
    expect(parallel.title).toBe("Dashboard Feed");
  });

  it("emits a separate entry for interceptor routes (.)folder", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const interceptor = byRoute(routes, "/(.)modal");
    expect(interceptor.is_interceptor).toBe(true);
    expect(interceptor.title).toBe("Modal Interceptor");
  });

  it("skips the entire (auth) route group", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const loginLike = routes.filter(
      (r) => r.route === "/login" || r.source_file.includes("(auth)")
    );
    expect(loginLike).toEqual([]);
  });

  it("extracts title from metadata.title when present", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const quotes = byRoute(routes, "/quotes");
    expect(quotes.title).toBe("Quotes");
    expect(quotes.title_source).toBe("metadata");
  });

  it("extracts title from @journey-title JSDoc when metadata missing", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const detail = byRoute(routes, "/quotes/[id]");
    expect(detail.title).toBe("Quote Detail");
    expect(detail.title_source).toBe("jsdoc");
  });

  it("falls back to first <h1> literal text", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const cost = byRoute(routes, "/quotes/[id]/cost-analysis");
    expect(cost.title_source).toBe("h1");
  });

  it("falls back to route basename (capitalised) when nothing else matches", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const shop = byRoute(routes, "/shop/[[...slug]]");
    expect(shop.title).toBe("Shop");
    expect(shop.title_source).toBe("basename");
  });

  it("builds parent-child tree from layout.tsx nesting", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const detail = byRoute(routes, "/quotes/[id]");
    const list = byRoute(routes, "/quotes");
    // /quotes/layout.tsx wraps /quotes/[id] → parent is /quotes
    expect(detail.parent_node_id).toBe(list.node_id);
    expect(list.children).toContain(detail.node_id);
  });

  it("emits node_id with 'app:' prefix for every route", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    for (const r of routes) {
      expect(r.node_id.startsWith("app:")).toBe(true);
    }
  });

  it("produces deterministic output (two runs byte-identical)", async () => {
    const a = await parseRoutes(FIXTURES_ROOT);
    const b = await parseRoutes(FIXTURES_ROOT);
    expect(JSON.stringify(a)).toBe(JSON.stringify(b));
  });

  it("records the source_file path relative to the app root", async () => {
    const routes = await parseRoutes(FIXTURES_ROOT);
    const quotes = byRoute(routes, "/quotes");
    expect(quotes.source_file.endsWith("page.tsx")).toBe(true);
    // Must not contain absolute fixture path — relative to app root.
    expect(path.isAbsolute(quotes.source_file)).toBe(false);
  });
});
