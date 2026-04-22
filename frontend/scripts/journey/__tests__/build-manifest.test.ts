/**
 * build-manifest.ts — orchestrator tests (Task 7).
 *
 * Snapshot + determinism coverage for the merged journey manifest.
 *
 * Fixture layout (3 clusters, 8 app routes, 2 specs, 1 access-control.md):
 *   manifest/app/(app)/quotes/page.tsx
 *   manifest/app/(app)/quotes/[id]/page.tsx
 *   manifest/app/(app)/quotes/[id]/cost-analysis/page.tsx
 *   manifest/app/(app)/quotes/[id]/items/page.tsx
 *   manifest/app/(app)/customers/page.tsx
 *   manifest/app/(app)/customers/[id]/page.tsx
 *   manifest/app/(app)/suppliers/page.tsx
 *   manifest/app/(app)/suppliers/[id]/page.tsx
 *   manifest/app/(auth)/login/page.tsx   — must be excluded (Req 1.4)
 *   manifest/specs/quote-detail/requirements.md
 *   manifest/specs/customers-spec/requirements.md
 *   manifest/steering/access-control.md
 */
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, it, expect, beforeAll } from "vitest";

import { buildManifest, writeManifest } from "../build-manifest";
import type { JourneyManifest, JourneyNode } from "../../../src/entities/journey/types";

const FIXTURE_ROOT = path.resolve(__dirname, "fixtures", "manifest");
const APP_ROOT = path.join(FIXTURE_ROOT, "app");
const SPECS_ROOT = path.join(FIXTURE_ROOT, "specs");
const ACCESS_CONTROL = path.join(FIXTURE_ROOT, "steering", "access-control.md");

/**
 * Fixed commit + timestamp so the snapshot is byte-identical across runs.
 * These two fields are the only non-deterministic inputs in the manifest.
 */
const FIXED_COMMIT = "0000000000000000000000000000000000000000";
const FIXED_TIMESTAMP = "2026-04-22T00:00:00.000Z";

async function build(): Promise<JourneyManifest> {
  return buildManifest({
    appRoot: APP_ROOT,
    specsRoot: SPECS_ROOT,
    accessControlPath: ACCESS_CONTROL,
    repoRoot: FIXTURE_ROOT,
    commit: FIXED_COMMIT,
    generatedAt: FIXED_TIMESTAMP,
  });
}

describe("build-manifest", () => {
  let manifest: JourneyManifest;

  beforeAll(async () => {
    manifest = await build();
  });

  it("excludes routes inside (auth) group — Req 1.4", () => {
    const routes = manifest.nodes.map((n) => n.route);
    expect(routes).not.toContain("/login");
  });

  it("includes exactly 8 authenticated routes across 3 clusters", () => {
    expect(manifest.nodes).toHaveLength(8);
    const clusterSlugs = new Set(manifest.nodes.map((n) => n.cluster));
    expect([...clusterSlugs].sort()).toEqual(
      ["customers", "quotes", "suppliers"].sort(),
    );
  });

  it("assigns clusters from the first route segment", () => {
    for (const node of manifest.nodes) {
      if (node.route.startsWith("/quotes")) expect(node.cluster).toBe("quotes");
      if (node.route.startsWith("/customers")) expect(node.cluster).toBe("customers");
      if (node.route.startsWith("/suppliers")) expect(node.cluster).toBe("suppliers");
    }
  });

  it("populates roles from the access-control matrix (cluster slug join)", () => {
    const quoteDetail = findNode(manifest, "app:/quotes/[id]");
    // Quotes cluster has catchAll=undefined in the fixture — `admin`, `top_manager`,
    // `head_of_sales`, `sales`, and the procurement/logistics/customs trio are
    // all visible per the access-control.md table.
    expect(quoteDetail.roles).toContain("admin");
    expect(quoteDetail.roles).toContain("sales");
    expect(quoteDetail.roles).toContain("procurement");

    const supplier = findNode(manifest, "app:/suppliers/[id]");
    // Suppliers section has "All other roles | No access", so sales/customs etc. excluded.
    expect(supplier.roles).toContain("admin");
    expect(supplier.roles).toContain("head_of_procurement");
    expect(supplier.roles).not.toContain("sales");
    expect(supplier.roles).not.toContain("customs");
  });

  it("binds stories via explicit frontmatter (priority 1)", () => {
    const quoteDetail = findNode(manifest, "app:/quotes/[id]");
    expect(quoteDetail.stories.length).toBeGreaterThanOrEqual(2);
    const actors = quoteDetail.stories.map((s) => s.actor).sort();
    expect(actors).toContain("sales");
    expect(actors).toContain("procurement");
  });

  it("binds stories via fuzzy slug match when no frontmatter (priority 2)", () => {
    const customers = findNode(manifest, "app:/customers");
    // 'customers-spec' slug fuzzy-matches /customers; story actor = sales.
    const customerStoryActors = customers.stories.map((s) => s.actor);
    expect(customerStoryActors).toContain("sales");
  });

  it("derives drill edges from parent_node_id", () => {
    const edge = manifest.edges.find(
      (e) => e.from === "app:/quotes/[id]" && e.to === "app:/quotes/[id]/items",
    );
    expect(edge).toBeDefined();
    expect(edge?.kind).toBe("drill");
  });

  it("produces sorted arrays — deterministic output (Req 1.10)", () => {
    const nodeIds = manifest.nodes.map((n) => n.node_id);
    const sorted = [...nodeIds].sort();
    expect(nodeIds).toEqual(sorted);

    const clusterIds = manifest.clusters.map((c) => c.id);
    const sortedClusters = [...clusterIds].sort();
    expect(clusterIds).toEqual(sortedClusters);
  });

  it("matches the committed snapshot (byte-identical output, Req 1.10)", () => {
    // Inline snapshot — vitest auto-writes on first green run then diffs afterwards.
    expect(manifest).toMatchSnapshot();
  });

  it("is byte-identical across two back-to-back builds", async () => {
    const a = await build();
    const b = await build();
    const sa = JSON.stringify(a, null, 2) + "\n";
    const sb = JSON.stringify(b, null, 2) + "\n";
    expect(sa).toEqual(sb);
  });

  it("writeManifest writes the serialised manifest to disk with trailing newline", async () => {
    const tmp = await fs.mkdtemp(path.join(os.tmpdir(), "journey-manifest-"));
    const out = path.join(tmp, "journey-manifest.json");
    try {
      await writeManifest({
        appRoot: APP_ROOT,
        specsRoot: SPECS_ROOT,
        accessControlPath: ACCESS_CONTROL,
        repoRoot: FIXTURE_ROOT,
        commit: FIXED_COMMIT,
        generatedAt: FIXED_TIMESTAMP,
        outputPath: out,
      });
      const onDisk = await fs.readFile(out, "utf8");
      expect(onDisk.endsWith("\n")).toBe(true);
      // Re-parse must round-trip to the same JSON.
      expect(JSON.parse(onDisk)).toEqual(manifest);
    } finally {
      await fs.rm(tmp, { recursive: true, force: true });
    }
  });
});

function findNode(manifest: JourneyManifest, nodeId: string): JourneyNode {
  const node = manifest.nodes.find((n) => n.node_id === nodeId);
  if (!node) {
    throw new Error(
      `Expected node '${nodeId}' not found. Got: ${manifest.nodes
        .map((n) => n.node_id)
        .join(", ")}`,
    );
  }
  return node;
}
