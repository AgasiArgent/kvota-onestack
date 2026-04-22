/**
 * build-manifest.ts — orchestrator for the three journey parsers.
 *
 * Stitches `parse-routes.ts` + `parse-specs.ts` + `parse-roles.ts` into a single
 * deterministic `frontend/public/journey-manifest.json` that the `/journey` UI
 * and the `GET /api/journey/nodes` aggregate consume.
 *
 * Spec references: `.kiro/specs/customer-journey-map/design.md` §4.6 / §5.1 and
 * `requirements.md` Req 1.1, 1.2, 1.3, 1.8, 1.10, 1.11, 1.12.
 *
 * ---------------------------------------------------------------------------
 * Cluster slug convention
 * ---------------------------------------------------------------------------
 * `parse-routes.ts` does NOT emit `cluster` — it is the orchestrator's job.
 * `parse-roles.ts` emits cluster slugs by slugifying `### <Entity>` headings
 * from `.kiro/steering/access-control.md`:
 *   `customers` | `quotes` | `specifications` | `suppliers` | `deals` |
 *   `payments_and_financials`, etc.
 *
 * To make route-derived clusters agree with role-matrix cluster keys, this
 * orchestrator derives a node's cluster from the FIRST non-group path segment
 * of its route, lowercased with non-`[a-z0-9_]` replaced by `_`. Examples:
 *   `/quotes`              → `quotes`
 *   `/quotes/[id]`         → `quotes`
 *   `/shop/[[...slug]]`    → `shop`
 *   `/dashboard/@feed`     → `dashboard`
 *   `/(.)modal`            → `modal` (strip interceptor parenthetical)
 *   `/`                    → `root`
 *
 * This keeps the two parsers reconcileable without a hand-maintained mapping
 * table: if the Next.js folder structure and `access-control.md` use the same
 * domain words (which they do in OneStack), the slugs align naturally. Any
 * mismatch surfaces in the role-visibility join below — the role is simply
 * excluded from that node, which is the correct conservative default.
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

import type {
  JourneyCluster,
  JourneyEdge,
  JourneyManifest,
  JourneyNode,
  JourneyStory,
  RoleSlug,
} from "../../src/entities/journey/types";

import { parseRoutes, type ParsedRoute } from "./parse-routes";
import { parseSpecs } from "./parse-specs";
import { parseRoles, type RoleVisibilityMatrix } from "./parse-roles";

const execFileAsync = promisify(execFile);

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface BuildManifestOptions {
  /** Absolute path to the Next.js App Router root, e.g. `frontend/src/app`. */
  readonly appRoot: string;
  /** Absolute path to the `.kiro/specs` directory. */
  readonly specsRoot: string;
  /** Absolute path to `.kiro/steering/access-control.md`. */
  readonly accessControlPath: string;
  /** Absolute path of the directory from which `source_file` paths are made relative. */
  readonly repoRoot: string;
  /** Optional fixed git SHA — used by tests to get deterministic output. */
  readonly commit?: string;
  /** Optional fixed ISO timestamp — used by tests to get deterministic output. */
  readonly generatedAt?: string;
}

/** Build the full manifest in memory. Pure function — no filesystem writes. */
export async function buildManifest(
  options: BuildManifestOptions,
): Promise<JourneyManifest> {
  const [routes, roleMatrix] = await Promise.all([
    parseRoutes(options.appRoot),
    parseRoles(options.accessControlPath),
  ]);

  const knownRoutes = routes.map((r) => r.route);
  const specs = await parseSpecs({
    specsRoot: options.specsRoot,
    knownRoutes,
  });

  const appRootRel = toPosix(path.relative(options.repoRoot, options.appRoot));
  const nodes = routes.map((route): JourneyNode =>
    buildNode(route, appRootRel, roleMatrix, specs.storiesByNodeId),
  );

  const clusters = buildClusters(nodes);
  const edges = buildEdges(nodes);

  // Deterministic sorts — every array in the manifest is ordered so two runs
  // over the same sources produce byte-identical output (Req 1.10).
  nodes.sort((a, b) => compare(a.node_id, b.node_id));
  clusters.sort((a, b) => compare(a.id, b.id));
  edges.sort(compareEdges);

  const commit = options.commit ?? (await resolveCommit(options.repoRoot));
  // `generated_at` defaults to the commit's authored timestamp rather than
  // wall-clock time so two builds of the same tree produce byte-identical
  // output (Req 1.10 / CI stale-check in §5.1).
  const generatedAt =
    options.generatedAt ?? (await resolveCommitTimestamp(options.repoRoot, commit));

  return {
    version: 1,
    generated_at: generatedAt,
    commit,
    nodes,
    edges,
    clusters,
  };
}

export interface WriteManifestOptions extends BuildManifestOptions {
  /** Absolute path of the output file, e.g. `frontend/public/journey-manifest.json`. */
  readonly outputPath: string;
}

/**
 * Build and write the manifest to disk. Output is `JSON.stringify(..., 2) + '\n'`
 * — 2-space indent plus a terminating newline, matching the repo convention and
 * making the file idempotent under `git add` on a POSIX system.
 */
export async function writeManifest(
  options: WriteManifestOptions,
): Promise<JourneyManifest> {
  const manifest = await buildManifest(options);
  const serialised = JSON.stringify(manifest, null, 2) + "\n";
  await fs.mkdir(path.dirname(options.outputPath), { recursive: true });
  await fs.writeFile(options.outputPath, serialised, "utf8");
  return manifest;
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

/**
 * Derive a cluster slug from a Next.js route path — the first non-group
 * segment, lowercased, with non-`[a-z0-9_]` replaced by `_`. See the module
 * docstring for the rationale and worked examples.
 */
function deriveCluster(route: string): string {
  if (route === "/" || route === "") return "root";
  const segments = route.split("/").filter((seg) => seg.length > 0);
  for (const rawSeg of segments) {
    // Strip interceptor prefix `(.)`, `(..)`, `(...)` if present.
    const stripped = rawSeg.replace(/^\(\.{1,3}\)/, "");
    // Skip pure route groups like `(app)` — they never produce a cluster word.
    if (/^\([^.)][^)]*\)$/.test(stripped)) continue;
    // Skip parameterised segments at the root (e.g. `[id]` should never be the
    // first meaningful segment, but guard anyway).
    if (stripped.startsWith("[")) continue;
    // Strip leading `@` for parallel slots — the slot name is the cluster.
    const body = stripped.startsWith("@") ? stripped.slice(1) : stripped;
    const slug = body
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
    if (slug.length > 0) return slug;
  }
  return "root";
}

function buildNode(
  route: ParsedRoute,
  appRootRel: string,
  roleMatrix: RoleVisibilityMatrix,
  storiesByNodeId: Readonly<Record<string, readonly JourneyStory[]>>,
): JourneyNode {
  const cluster = deriveCluster(route.route);
  const roles = collectRolesForCluster(cluster, roleMatrix);
  const sourceFile = appRootRel ? `${appRootRel}/${route.source_file}` : route.source_file;
  const rawStories = storiesByNodeId[route.node_id] ?? [];
  // Deduplicate identical stories (same spec may fuzzy-match multiple routes)
  // and sort deterministically.
  const stories = dedupeStories(rawStories).sort(compareStories);

  return {
    node_id: route.node_id,
    route: route.route,
    title: route.title,
    cluster,
    source_files: [sourceFile],
    roles,
    stories,
    parent_node_id: route.parent_node_id,
    children: [...route.children].sort(),
  };
}

function collectRolesForCluster(
  cluster: string,
  matrix: RoleVisibilityMatrix,
): readonly RoleSlug[] {
  const roles: RoleSlug[] = [];
  for (const roleKey of Object.keys(matrix) as RoleSlug[]) {
    const visibility = matrix[roleKey];
    if (visibility[cluster] === true) roles.push(roleKey);
  }
  roles.sort();
  return roles;
}

function dedupeStories(stories: readonly JourneyStory[]): JourneyStory[] {
  const seen = new Set<string>();
  const out: JourneyStory[] = [];
  for (const s of stories) {
    const key = `${s.ref} ${s.actor} ${s.goal} ${s.spec_file}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(s);
  }
  return out;
}

function compareStories(a: JourneyStory, b: JourneyStory): number {
  return (
    compare(a.spec_file, b.spec_file) ||
    compare(a.ref, b.ref) ||
    compare(a.actor, b.actor) ||
    compare(a.goal, b.goal)
  );
}

function buildClusters(nodes: readonly JourneyNode[]): JourneyCluster[] {
  const unique = new Set<string>();
  for (const n of nodes) unique.add(n.cluster);
  return [...unique].map((id) => ({
    id,
    label: labelFromSlug(id),
    colour: colourForCluster(id),
  }));
}

function labelFromSlug(slug: string): string {
  if (slug === "root") return "Root";
  return slug
    .split("_")
    .filter((w) => w.length > 0)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/**
 * Deterministic colour per cluster slug — a stable hash maps each slug to one
 * of a small palette. Keeping colour-picking in the manifest (rather than the
 * UI) means the colours don't churn when unrelated UI code is edited.
 */
function colourForCluster(slug: string): string {
  const palette = [
    "#5B8DEF", // blue
    "#F59E0B", // amber
    "#10B981", // emerald
    "#EF4444", // red
    "#8B5CF6", // violet
    "#EC4899", // pink
    "#14B8A6", // teal
    "#64748B", // slate
  ];
  let hash = 0;
  for (let i = 0; i < slug.length; i++) {
    hash = (hash * 31 + slug.charCodeAt(i)) >>> 0;
  }
  return palette[hash % palette.length];
}

function buildEdges(nodes: readonly JourneyNode[]): JourneyEdge[] {
  const edges: JourneyEdge[] = [];
  for (const node of nodes) {
    if (node.parent_node_id !== null) {
      edges.push({
        from: node.parent_node_id,
        to: node.node_id,
        kind: "drill",
      });
    }
  }
  return edges;
}

function compareEdges(a: JourneyEdge, b: JourneyEdge): number {
  return (
    compare(a.from, b.from) || compare(a.to, b.to) || compare(a.kind, b.kind)
  );
}

function compare(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

function toPosix(p: string): string {
  return p.split(path.sep).join("/");
}

async function resolveCommit(repoRoot: string): Promise<string> {
  try {
    const { stdout } = await execFileAsync("git", ["rev-parse", "HEAD"], {
      cwd: repoRoot,
    });
    return stdout.trim();
  } catch {
    // Not a git repo, shallow checkout without .git, etc. — degrade gracefully.
    return "unknown";
  }
}

async function resolveCommitTimestamp(
  repoRoot: string,
  commit: string,
): Promise<string> {
  if (commit === "unknown") return "1970-01-01T00:00:00.000Z";
  try {
    // %aI = author date, strict ISO-8601. Matches the commit exactly so the
    // output is reproducible on CI (same SHA → same timestamp).
    const { stdout } = await execFileAsync(
      "git",
      ["show", "-s", "--format=%aI", commit],
      { cwd: repoRoot },
    );
    const raw = stdout.trim();
    // Normalise to UTC ISO-8601 with milliseconds so the field shape is stable
    // regardless of the committer's local timezone offset format.
    const parsed = new Date(raw);
    if (Number.isNaN(parsed.getTime())) return "1970-01-01T00:00:00.000Z";
    return parsed.toISOString();
  } catch {
    return "1970-01-01T00:00:00.000Z";
  }
}

// ---------------------------------------------------------------------------
// CLI entry point
// ---------------------------------------------------------------------------

/**
 * Invoked via `npm run journey:build` (wired in `frontend/package.json`).
 * Repo layout assumption: this file sits at `frontend/scripts/journey/` inside
 * the repo, so the repo root is three levels up.
 */
async function main(): Promise<void> {
  const frontendRoot = path.resolve(__dirname, "..", "..");
  const repoRoot = path.resolve(frontendRoot, "..");

  await writeManifest({
    appRoot: path.join(frontendRoot, "src", "app"),
    specsRoot: path.join(repoRoot, ".kiro", "specs"),
    accessControlPath: path.join(
      repoRoot,
      ".kiro",
      "steering",
      "access-control.md",
    ),
    repoRoot,
    outputPath: path.join(frontendRoot, "public", "journey-manifest.json"),
  });
}

// Only auto-run when invoked directly (not when imported by tests).
// `require.main === module` is the Node idiom that works under tsx/ts-node.
if (require.main === module) {
  main().catch((err) => {
    console.error("[build-manifest] failed:", err);
    process.exitCode = 1;
  });
}
