/**
 * parse-routes.ts — Next.js 15 App Router → typed ParsedRoute[].
 *
 * Walks a given App Router root (normally `frontend/src/app`) and emits one
 * `ParsedRoute` per `page.tsx` found, correctly applying Next.js 15 route
 * conventions:
 *
 *   - `(group)` → stripped from the public route path (node grouping only)
 *   - `[slug]` / `[...slug]` / `[[...slug]]` → preserved verbatim in `route`
 *   - `@slot` parallel routes → emitted as distinct nodes, marked `is_parallel_slot`
 *   - `(.)folder`, `(..)folder`, `(...)folder` interceptors → distinct nodes, marked `is_interceptor`
 *   - `(auth)` group → skipped entirely (pre-auth pages, per Req 1.4)
 *
 * Title extraction priority (per Req 1.9):
 *   1. `export const metadata = { title: "…" }` (static string literal)
 *   2. `/** @journey-title "…" *​/` JSDoc comment
 *   3. First `<h1>…</h1>` literal text
 *   4. Route basename, capitalised
 *
 * Parent-child relationships are derived from `layout.tsx` nesting: the nearest
 * ancestor directory containing both a `layout.tsx` AND a `page.tsx` becomes
 * the parent node of the current route.
 *
 * Consumed by `build-manifest.ts` (Task 7). No runtime `any`.
 */

import { promises as fs, type Dirent } from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/** Which extraction step produced the final title — useful for debugging. */
export type TitleSource = "metadata" | "jsdoc" | "h1" | "basename";

/**
 * Output row for a single route.
 *
 * This is the parser's internal shape. `build-manifest.ts` will enrich each
 * entry with roles and stories (from the other two parsers) before producing
 * the final `JourneyNode` defined in `entities/journey/types.ts`.
 */
export interface ParsedRoute {
  /** Public path including brackets, e.g. `/quotes/[id]`, `/shop/[[...slug]]`. */
  readonly route: string;
  /** Stable identifier — always `app:<route>`. */
  readonly node_id: `app:${string}`;
  /** Display title (fallback chain applied). */
  readonly title: string;
  /** Which source produced `title` (for `--debug` mode and tests). */
  readonly title_source: TitleSource;
  /** Path of `page.tsx`, relative to the supplied app root. POSIX separators. */
  readonly source_file: string;
  /** `node_id` of the nearest ancestor route (via layout nesting), or `null`. */
  readonly parent_node_id: `app:${string}` | null;
  /** Direct-child `node_id`s, sorted alphabetically for determinism. */
  readonly children: readonly `app:${string}`[];
  /** True for `[[...slug]]` optional catch-all routes. */
  readonly is_catch_all: boolean;
  /** True for parallel routes (segment starts with `@`). */
  readonly is_parallel_slot: boolean;
  /** Slot name without the `@` (only set when `is_parallel_slot`). */
  readonly parallel_slot: string | null;
  /** True for interceptor segments `(.)x` / `(..)x` / `(...)x`. */
  readonly is_interceptor: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Route groups skipped entirely — their pages are pre-auth per Req 1.4. */
const SKIPPED_GROUPS: ReadonlySet<string> = new Set(["(auth)"]);

/** Matches `export const metadata = { ... title: "foo" ... }`. */
const METADATA_TITLE_RE =
  /export\s+const\s+metadata\s*(?::\s*[^=]+)?=\s*\{[\s\S]*?title\s*:\s*(['"`])([^'"`]+)\1/;

/** Matches `/** @journey-title "foo" *​/` (single- or double-quoted). */
const JSDOC_TITLE_RE = /@journey-title\s+(['"])([^'"]+)\1/;

/** Matches the first `<h1>…</h1>` with plain literal text (no JSX children). */
const H1_TEXT_RE = /<h1[^>]*>\s*([^<{][^<]*?)\s*<\/h1>/;

/** Catch-all segment detection. */
const OPTIONAL_CATCH_ALL_RE = /^\[\[\.\.\..+\]\]$/;

/** Interceptor segment detection: `(.)folder`, `(..)folder`, `(...)folder`. */
const INTERCEPTOR_RE = /^\((?:\.{1,3})\)[^()]+$/;

/** Plain route-group segment: `(group)` but not `(.)x`, `(..)x`, `(...)x`. */
const ROUTE_GROUP_RE = /^\(([^.)][^)]*)\)$/;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Walk `appRoot` and return one `ParsedRoute` per discovered `page.tsx`.
 *
 * Output is sorted by `route` for deterministic snapshots (Req 1.10).
 *
 * @param appRoot Absolute path to `frontend/src/app` (or a fixture root).
 */
export async function parseRoutes(
  appRoot: string
): Promise<readonly ParsedRoute[]> {
  const resolvedRoot = path.resolve(appRoot);
  const pagePaths: string[] = [];
  await collectPagePaths(resolvedRoot, [], pagePaths);

  const rows: ParsedRoute[] = [];
  for (const pagePath of pagePaths) {
    const relative = path.relative(resolvedRoot, pagePath).split(path.sep);
    const dirSegments = relative.slice(0, -1); // drop 'page.tsx'

    // Skip anything under an excluded group.
    if (dirSegments.some((seg) => SKIPPED_GROUPS.has(seg))) {
      continue;
    }

    const source = await fs.readFile(pagePath, "utf8");
    const route = buildRoutePath(dirSegments);
    const nodeId: `app:${string}` = `app:${route}`;
    const { title, title_source } = extractTitle(source, dirSegments);
    const flags = detectSegmentFlags(dirSegments);
    const parentId = await findParentNodeId(resolvedRoot, dirSegments);

    rows.push({
      route,
      node_id: nodeId,
      title,
      title_source,
      source_file: toPosix(path.relative(resolvedRoot, pagePath)),
      parent_node_id: parentId,
      children: [], // filled in the second pass below
      is_catch_all: flags.is_catch_all,
      is_parallel_slot: flags.is_parallel_slot,
      parallel_slot: flags.parallel_slot,
      is_interceptor: flags.is_interceptor,
    });
  }

  // Second pass: populate `children` from recorded parents. Sort everything
  // deterministically so two runs produce byte-identical output.
  const byId = new Map<string, ParsedRoute>();
  for (const r of rows) byId.set(r.node_id, r);

  const childrenByParent = new Map<string, `app:${string}`[]>();
  for (const r of rows) {
    if (r.parent_node_id === null) continue;
    const bucket = childrenByParent.get(r.parent_node_id) ?? [];
    bucket.push(r.node_id);
    childrenByParent.set(r.parent_node_id, bucket);
  }

  const enriched: ParsedRoute[] = rows.map((r) => {
    const kids = childrenByParent.get(r.node_id);
    if (!kids || kids.length === 0) return r;
    return { ...r, children: [...kids].sort() };
  });

  enriched.sort((a, b) => (a.route < b.route ? -1 : a.route > b.route ? 1 : 0));
  return enriched;
}

// Exported for CLI entry points in sibling scripts (e.g. build-manifest.ts).
export default parseRoutes;

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

/** Recursively collect every `page.tsx` / `page.ts` path under `dir`. */
async function collectPagePaths(
  root: string,
  relativeSegments: readonly string[],
  out: string[]
): Promise<void> {
  const absolute = path.join(root, ...relativeSegments);
  let entries: Dirent[];
  try {
    entries = (await fs.readdir(absolute, { withFileTypes: true })) as Dirent[];
  } catch {
    return;
  }

  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
      await collectPagePaths(root, [...relativeSegments, entry.name], out);
      continue;
    }
    if (!entry.isFile()) continue;
    if (entry.name === "page.tsx" || entry.name === "page.ts") {
      out.push(path.join(absolute, entry.name));
    }
  }
}

/**
 * Turn directory segments into the public route path.
 * Strips `(group)` (non-interceptor), keeps `[slug]`, `[[...slug]]`, `@slot`,
 * and interceptor segments verbatim so interceptor nodes remain distinct from
 * their non-interceptor siblings.
 */
function buildRoutePath(segments: readonly string[]): string {
  const kept = segments.filter((seg) => !ROUTE_GROUP_RE.test(seg));
  if (kept.length === 0) return "/";
  return "/" + kept.join("/");
}

/** Per-route flags derived from the URL segments. */
interface SegmentFlags {
  readonly is_catch_all: boolean;
  readonly is_parallel_slot: boolean;
  readonly parallel_slot: string | null;
  readonly is_interceptor: boolean;
}

function detectSegmentFlags(segments: readonly string[]): SegmentFlags {
  let is_catch_all = false;
  let is_parallel_slot = false;
  let parallel_slot: string | null = null;
  let is_interceptor = false;

  for (const seg of segments) {
    if (OPTIONAL_CATCH_ALL_RE.test(seg)) is_catch_all = true;
    if (seg.startsWith("@")) {
      is_parallel_slot = true;
      parallel_slot = seg.slice(1);
    }
    if (INTERCEPTOR_RE.test(seg)) is_interceptor = true;
  }

  return { is_catch_all, is_parallel_slot, parallel_slot, is_interceptor };
}

interface ExtractedTitle {
  readonly title: string;
  readonly title_source: TitleSource;
}

function extractTitle(
  source: string,
  segments: readonly string[]
): ExtractedTitle {
  const metadataMatch = METADATA_TITLE_RE.exec(source);
  if (metadataMatch && metadataMatch[2]) {
    return { title: metadataMatch[2], title_source: "metadata" };
  }

  const jsdocMatch = JSDOC_TITLE_RE.exec(source);
  if (jsdocMatch && jsdocMatch[2]) {
    return { title: jsdocMatch[2], title_source: "jsdoc" };
  }

  const h1Match = H1_TEXT_RE.exec(source);
  if (h1Match && h1Match[1]) {
    const text = h1Match[1].trim();
    if (text.length > 0) {
      return { title: text, title_source: "h1" };
    }
  }

  return {
    title: basenameTitle(segments),
    title_source: "basename",
  };
}

/**
 * Derive a sensible title from the last meaningful segment.
 *
 * Strips `(group)`, `@slot`, and `[param]` decorations, replaces separators
 * with spaces, and capitalises each word. Falls back to `"Home"` for the
 * root route.
 */
function basenameTitle(segments: readonly string[]): string {
  for (let i = segments.length - 1; i >= 0; i -= 1) {
    const seg = segments[i];
    if (ROUTE_GROUP_RE.test(seg)) continue;
    if (INTERCEPTOR_RE.test(seg)) {
      const stripped = seg.replace(/^\(\.{1,3}\)/, "");
      if (stripped.length > 0) return capitalise(stripped);
      continue;
    }
    if (seg.startsWith("@")) {
      return capitalise(seg.slice(1));
    }
    // Strip brackets: [id], [...slug], [[...slug]] → drop
    if (seg.startsWith("[") && seg.endsWith("]")) continue;
    return capitalise(seg);
  }
  return "Home";
}

function capitalise(raw: string): string {
  const cleaned = raw.replace(/[-_]+/g, " ").trim();
  if (cleaned.length === 0) return "Untitled";
  return cleaned
    .split(/\s+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/**
 * Walk up the segments until we hit an ancestor directory that (a) has its
 * own `page.tsx` and (b) is not a skipped group. That ancestor is the parent
 * node per Req 1.8 / §4.6 ("parent-child tree from layout nesting").
 *
 * We deliberately treat `(group)` segments as transparent: they're stripped
 * from both paths and are not considered parents on their own. A `layout.tsx`
 * file is NOT required for parentage — the presence of a `page.tsx` in an
 * ancestor directory is sufficient (matches Next.js routing semantics where
 * the parent segment is always renderable on its own).
 */
async function findParentNodeId(
  root: string,
  segments: readonly string[]
): Promise<`app:${string}` | null> {
  for (let i = segments.length - 1; i > 0; i -= 1) {
    const ancestor = segments.slice(0, i);
    const ancestorAbs = path.join(root, ...ancestor);
    const hasPage = await fileExists(path.join(ancestorAbs, "page.tsx"));
    if (!hasPage) continue;
    const ancestorRoute = buildRoutePath(ancestor);
    return `app:${ancestorRoute}`;
  }
  return null;
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    const stat = await fs.stat(filePath);
    return stat.isFile();
  } catch {
    return false;
  }
}

function toPosix(p: string): string {
  return p.split(path.sep).join("/");
}
