/**
 * backfill-related-routes — one-time script that proposes `related_routes:`
 * frontmatter additions for existing `.kiro/specs/ **\/requirements.md` files.
 *
 * This script does NOT write files; it outputs a review patch that an admin
 * applies manually with `git apply`.
 *
 * Workflow:
 *   1. Reads `frontend/public/journey-manifest.json` for the list of known
 *      routes.
 *   2. Walks `.kiro/specs/ **\/requirements.md`.
 *   3. Skips specs that already have `related_routes:` in their frontmatter.
 *   4. Extracts path-like tokens from the body (e.g. `/quotes/[id]`,
 *      `/customers`) and keeps only those that match a known route exactly.
 *   5. For each spec with ≥ 1 matched route, generates a unified-diff hunk that
 *      prepends a `related_routes:` frontmatter block to the file.
 *   6. Writes the combined patch to
 *      `docs/superpowers/backfill-related-routes-<YYYY-MM-DD>.patch`.
 *
 * An admin reviews the patch and applies it with `git apply <patch>`.
 *
 * Spec refs: `customer-journey-map/requirements.md` Req 1.7;
 *            `customer-journey-map/design.md` §4.6.
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import matter from "gray-matter";

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface BackfillOptions {
  /** Absolute path to the directory containing all spec sub-directories. */
  readonly specsRoot: string;
  /** List of known routes (from `journey-manifest.json`) to match against. */
  readonly knownRoutes: readonly string[];
  /** Absolute path of the directory where the patch file is written. */
  readonly outputDir: string;
  /** ISO date (YYYY-MM-DD) embedded in the patch file name. */
  readonly today: string;
  /**
   * Optional override for the `a/` / `b/` path prefix in the diff headers.
   * Defaults to the spec file path relative to `specsRoot`, prefixed with
   * `.kiro/specs/` so the patch applies cleanly when `git apply` runs from the
   * repo root. Tests pass a fixture-relative prefix.
   */
  readonly diffPathPrefix?: string;
}

export interface BackfillEntry {
  /** Absolute path to the markdown file that would be patched. */
  readonly specFile: string;
  /** Routes proposed for addition to `related_routes:`. */
  readonly routes: readonly string[];
}

export interface BackfillResult {
  /** Absolute path of the written patch file. */
  readonly patchPath: string;
  /** Number of markdown files scanned. */
  readonly scanned: number;
  /** Patch entries produced — one per spec file getting an addition. */
  readonly entries: readonly BackfillEntry[];
  /** Always 0 — the script never modifies source files. */
  readonly filesModified: 0;
}

export async function generateBackfillPatch(
  options: BackfillOptions,
): Promise<BackfillResult> {
  const { specsRoot, knownRoutes, outputDir, today } = options;

  const knownRouteSet = new Set(knownRoutes);
  const mdFiles = await listMarkdownFiles(specsRoot);
  const entries: BackfillEntry[] = [];

  for (const mdPath of mdFiles) {
    const raw = await fs.readFile(mdPath, "utf8");
    const parsed = matter(raw);
    const frontmatter = parsed.data as { related_routes?: unknown };

    // Skip specs that already have `related_routes:` frontmatter, regardless
    // of whether it is an array or empty — an admin already reviewed them.
    if (frontmatter.related_routes !== undefined) continue;

    const matched = extractKnownRoutes(parsed.content, knownRouteSet);
    if (matched.length === 0) continue;

    entries.push({ specFile: mdPath, routes: matched });
  }

  // Deterministic order — sort by spec file path so re-runs produce
  // byte-identical patches (reviewable diffs).
  entries.sort((a, b) => (a.specFile < b.specFile ? -1 : a.specFile > b.specFile ? 1 : 0));

  const patchBody = entries
    .map((entry) => renderDiffHunk(entry, specsRoot, options.diffPathPrefix))
    .join("");

  await fs.mkdir(outputDir, { recursive: true });
  const patchPath = path.join(outputDir, `backfill-related-routes-${today}.patch`);
  await fs.writeFile(patchPath, patchBody, "utf8");

  return {
    patchPath,
    scanned: mdFiles.length,
    entries,
    filesModified: 0,
  };
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

/**
 * Extract path-like tokens from markdown body and keep only those that match
 * a known route exactly. Matching is exact on the full path — no prefix
 * matching — because the backfill output should be reviewable without
 * guesswork.
 *
 * Regex explanation:
 *   /[a-z] — slash + lower-case letter (filters out URLs like `http://`, file
 *            paths starting with digits, etc.)
 *   [a-z0-9\-_/\[\]]* — subsequent path characters including Next.js dynamic
 *                      segments `[id]`
 */
function extractKnownRoutes(
  body: string,
  knownRouteSet: ReadonlySet<string>,
): string[] {
  // Strip URLs first (http://, https://) so their path part does not leak in.
  const sanitised = body.replace(/https?:\/\/\S+/gi, "");
  const pattern = /\/[a-z][a-z0-9\-_/\[\]]*/gi;
  const matches = sanitised.match(pattern) ?? [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of matches) {
    // Trim trailing punctuation the regex may have captured (e.g. period at
    // end of sentence, though [a-z0-9\-_/\[\]] already excludes it).
    const candidate = raw.replace(/[.,;:!?)]+$/g, "");
    if (knownRouteSet.has(candidate) && !seen.has(candidate)) {
      seen.add(candidate);
      out.push(candidate);
    }
  }
  // Deterministic order for reviewable patches.
  out.sort();
  return out;
}

async function listMarkdownFiles(dir: string): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const results: string[] = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isFile() && entry.name === "requirements.md") {
      results.push(full);
    } else if (entry.isDirectory()) {
      const nested = await listMarkdownFiles(full);
      results.push(...nested);
    }
  }
  results.sort();
  return results;
}

/**
 * Render a minimal unified-diff hunk that prepends a `related_routes:`
 * frontmatter block to the top of the file. The patch is designed to apply
 * cleanly to a file that currently has NO frontmatter (existing specs with
 * frontmatter are skipped earlier).
 *
 * Hunk format (the first existing line is a CONTEXT line, not removed):
 *   @@ -1 +1,N @@
 *   +---
 *   +related_routes:
 *   +  - /route1
 *   +  - /route2
 *   +---
 *   +
 *    <existing first line>
 *
 * We use a single-line context window so the patch applies robustly regardless
 * of later file edits (as long as line 1 still matches).
 */
function renderDiffHunk(
  entry: BackfillEntry,
  specsRoot: string,
  diffPathPrefix: string | undefined,
): string {
  // Compute the in-diff path. Default: relative to a repo root whose layout
  // matches the production tree — `.kiro/specs/<slug>/requirements.md`.
  const rel = path.relative(specsRoot, entry.specFile);
  const diffPath = diffPathPrefix !== undefined
    ? path.join(diffPathPrefix, rel)
    : path.join(".kiro", "specs", rel);
  const posixPath = diffPath.split(path.sep).join("/");

  // Build the frontmatter block to prepend (each entry is one new line).
  const addedLines = [
    "---",
    "related_routes:",
    ...entry.routes.map((r) => `  - ${r}`),
    "---",
    "",
  ];

  // The first existing line of the file is used as a CONTEXT line so the
  // insertion anchors cleanly to the top of the file. If the file starts with
  // frontmatter we would have already skipped it in `generateBackfillPatch`.
  const firstLine = readFirstLineSync(entry.specFile);

  const oldCount = 1; // the context line
  const newCount = addedLines.length + 1; // added lines + context line

  const header =
    `diff --git a/${posixPath} b/${posixPath}\n` +
    `--- a/${posixPath}\n` +
    `+++ b/${posixPath}\n` +
    `@@ -1,${oldCount} +1,${newCount} @@\n`;

  const body =
    addedLines.map((line) => `+${line}\n`).join("") +
    ` ${firstLine}\n`;

  return header + body;
}

function readFirstLineSync(file: string): string {
  // Small sync read — these files are ≤ a few hundred lines and we only need
  // the first line. Reading async would complicate renderDiffHunk's return
  // type for no measurable benefit.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const fsSync = require("node:fs") as typeof import("node:fs");
  const content = fsSync.readFileSync(file, "utf8");
  const newlineIdx = content.indexOf("\n");
  return newlineIdx === -1 ? content : content.slice(0, newlineIdx);
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

interface ManifestShape {
  readonly nodes: ReadonlyArray<{ readonly route: string }>;
}

async function loadKnownRoutesFromManifest(manifestPath: string): Promise<string[]> {
  const raw = await fs.readFile(manifestPath, "utf8");
  const parsed = JSON.parse(raw) as ManifestShape;
  const routes = parsed.nodes.map((n) => n.route);
  return [...new Set(routes)];
}

function isoToday(): string {
  const d = new Date();
  const year = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

async function main(): Promise<void> {
  const frontendRoot = path.resolve(__dirname, "..", "..");
  const repoRoot = path.resolve(frontendRoot, "..");
  const specsRoot = path.join(repoRoot, ".kiro", "specs");
  const manifestPath = path.join(frontendRoot, "public", "journey-manifest.json");
  const outputDir = path.join(repoRoot, "docs", "superpowers");

  const knownRoutes = await loadKnownRoutesFromManifest(manifestPath);
  const result = await generateBackfillPatch({
    specsRoot,
    knownRoutes,
    outputDir,
    today: isoToday(),
  });

  const patchRel = path.relative(repoRoot, result.patchPath);
  console.log(
    `${result.scanned} specs scanned, ${result.entries.length} patch entries generated, ${result.filesModified} files modified`,
  );
  console.log(`Patch written to: ${patchRel}`);
  console.log(`Review, then apply manually with: git apply ${patchRel}`);
}

if (require.main === module) {
  main().catch((err) => {
    console.error("[backfill-related-routes] failed:", err);
    process.exitCode = 1;
  });
}
