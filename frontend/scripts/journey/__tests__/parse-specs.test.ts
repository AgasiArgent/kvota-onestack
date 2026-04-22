import { describe, it, expect } from "vitest";
import path from "path";
import { parseSpecs } from "../parse-specs";

const FIXTURES_DIR = path.join(__dirname, "fixtures", "specs");

const KNOWN_ROUTES = [
  "/quotes",
  "/quotes/[id]",
  "/customers",
  "/dashboard",
];

describe("parse-specs", () => {
  it("binds a story to the explicit route from frontmatter `related_routes`", async () => {
    const result = await parseSpecs({
      specsRoot: FIXTURES_DIR,
      knownRoutes: KNOWN_ROUTES,
    });

    const quoteStories = result.storiesByNodeId["app:/quotes/[id]"] ?? [];
    const fromSpecA = quoteStories.filter((s) =>
      s.spec_file.includes("spec-a"),
    );
    expect(fromSpecA).toHaveLength(1);
    expect(fromSpecA[0]?.actor).toBe("admin");
    expect(fromSpecA[0]?.goal).toMatch(/manage quotes/);
  });

  it("fuzzy-matches by directory slug when no frontmatter is present", async () => {
    const result = await parseSpecs({
      specsRoot: FIXTURES_DIR,
      knownRoutes: KNOWN_ROUTES,
    });

    const quoteStories = result.storiesByNodeId["app:/quotes/[id]"] ?? [];
    const fromPhase5b = quoteStories.filter((s) =>
      s.spec_file.includes("phase-5b-quote-composition"),
    );
    expect(fromPhase5b.length).toBeGreaterThanOrEqual(1);
    expect(fromPhase5b[0]?.actor).toBe("procurement");
    expect(fromPhase5b[0]?.goal).toMatch(/collect/);
  });

  it("extracts actor and goal via `As <role>, I <verb> ...` heading", async () => {
    const result = await parseSpecs({
      specsRoot: FIXTURES_DIR,
      knownRoutes: KNOWN_ROUTES,
    });

    const customerStories = result.storiesByNodeId["app:/customers"] ?? [];
    const specC = customerStories.find((s) => s.spec_file.includes("spec-c"));
    expect(specC).toBeDefined();
    expect(specC?.actor).toBe("sales");
    expect(specC?.goal).toMatch(/create a new customer/);
  });

  it("routes unmatched specs to the `unbound` bucket", async () => {
    const result = await parseSpecs({
      specsRoot: FIXTURES_DIR,
      knownRoutes: KNOWN_ROUTES,
    });

    const unbound = result.unbound;
    const specDStories = unbound.filter((s) => s.spec_file.includes("spec-d"));
    expect(specDStories.length).toBeGreaterThanOrEqual(1);
    expect(specDStories[0]?.actor).toBe("admin");
    expect(specDStories[0]?.goal).toMatch(/zzznonexistent/);
  });
});
