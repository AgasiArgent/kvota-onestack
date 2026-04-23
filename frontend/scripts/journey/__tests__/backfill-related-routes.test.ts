import { describe, it, expect, beforeEach, afterEach } from "vitest";
import path from "path";
import fs from "fs/promises";
import os from "os";
import {
  generateBackfillPatch,
  type BackfillOptions,
} from "../backfill-related-routes";

const FIXTURES_DIR = path.join(__dirname, "fixtures", "backfill-specs");

const KNOWN_ROUTES = [
  "/quotes",
  "/quotes/[id]",
  "/customers",
  "/admin/users",
  "/dashboard",
];

describe("backfill-related-routes", () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "backfill-test-"));
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  async function runScript(overrides: Partial<BackfillOptions> = {}) {
    const opts: BackfillOptions = {
      specsRoot: FIXTURES_DIR,
      knownRoutes: KNOWN_ROUTES,
      outputDir: tempDir,
      today: "2026-04-22",
      ...overrides,
    };
    return generateBackfillPatch(opts);
  }

  it("emits a patch file named with today's ISO date", async () => {
    const result = await runScript();
    const expected = path.join(
      tempDir,
      "backfill-related-routes-2026-04-22.patch",
    );
    expect(result.patchPath).toBe(expected);
    const stat = await fs.stat(result.patchPath);
    expect(stat.isFile()).toBe(true);
  });

  it("adds a patch entry for spec-a with both /quotes/[id] and /customers", async () => {
    const result = await runScript();
    const patch = await fs.readFile(result.patchPath, "utf8");

    // Must contain a diff block for spec-a/requirements.md
    expect(patch).toMatch(
      /diff --git a\/.*spec-a\/requirements\.md b\/.*spec-a\/requirements\.md/,
    );
    // Must propose both routes
    expect(patch).toMatch(/\+\s*-\s+\/quotes\/\[id\]/);
    expect(patch).toMatch(/\+\s*-\s+\/customers/);
  });

  it("adds a patch entry for spec-b with /admin/users only", async () => {
    const result = await runScript();
    const patch = await fs.readFile(result.patchPath, "utf8");

    expect(patch).toMatch(
      /diff --git a\/.*spec-b\/requirements\.md b\/.*spec-b\/requirements\.md/,
    );
    expect(patch).toMatch(/\+\s*-\s+\/admin\/users/);
  });

  it("skips spec-c because related_routes frontmatter is already present", async () => {
    const result = await runScript();
    const patch = await fs.readFile(result.patchPath, "utf8");

    expect(patch).not.toMatch(/spec-c\/requirements\.md/);
    expect(result.entries.find((e) => e.specFile.includes("spec-c"))).toBeUndefined();
  });

  it("skips spec-d because no known route paths appear in the body", async () => {
    const result = await runScript();
    const patch = await fs.readFile(result.patchPath, "utf8");

    expect(patch).not.toMatch(/spec-d\/requirements\.md/);
    expect(result.entries.find((e) => e.specFile.includes("spec-d"))).toBeUndefined();
  });

  it("produces git-apply compatible output (starts with `diff --git`, has `@@` hunks)", async () => {
    const result = await runScript();
    const patch = await fs.readFile(result.patchPath, "utf8");

    expect(patch.startsWith("diff --git")).toBe(true);
    expect(patch).toMatch(/@@ /);
    // Every hunk header starts with `@@ -`
    expect(patch).toMatch(/^@@ -\d+,\d+ \+\d+,\d+ @@/m);
  });

  it("reports summary counts via return value", async () => {
    const result = await runScript();

    expect(result.scanned).toBe(4); // 4 fixture spec files
    expect(result.entries).toHaveLength(2); // spec-a + spec-b
    expect(result.filesModified).toBe(0); // script never writes to source tree
  });
});
