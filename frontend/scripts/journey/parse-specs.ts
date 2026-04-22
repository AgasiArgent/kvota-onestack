/**
 * parse-specs — reads `.kiro/specs/** /*.md`, extracts user stories,
 * and binds them to routes via frontmatter `related_routes:` or via fuzzy
 * directory-slug match against the known-routes list.
 *
 * Binding priority (per Requirement 1.6):
 *   1. Explicit `related_routes: [...]` in the markdown frontmatter.
 *   2. Fuzzy match: spec-directory slug words vs. route path segments
 *      (case-insensitive word overlap, no stemming).
 *   3. "unbound" bucket — surfaced in the UI for manual triage.
 *
 * Story extraction: `/^As (\w[\w_]*),\s*I\s+(.+)$/m` captures lines of the
 * form "As sales, I can …" → `{ actor: 'sales', goal: 'I can …' }`.
 */
import fs from "fs/promises";
import path from "path";
import matter from "gray-matter";
import type { JourneyNodeId, JourneyStory } from "../../src/entities/journey/types";

export interface ParseSpecsOptions {
  /** Absolute path to the directory that contains all spec sub-directories. */
  readonly specsRoot: string;
  /** All known route paths (e.g. '/quotes/[id]'), used for fuzzy matching and binding. */
  readonly knownRoutes: readonly string[];
}

export interface ParseSpecsResult {
  /** Stories grouped by `node_id` (`app:<route>`). */
  readonly storiesByNodeId: Readonly<Record<string, readonly JourneyStory[]>>;
  /** Stories that could not be bound to any known route. */
  readonly unbound: readonly JourneyStory[];
}

const STORY_RE = /^As (\w[\w_]*),\s*I\s+(.+)$/gm;

const PHASE_SLUG_NOISE = new Set([
  "phase",
  "v1",
  "v2",
  "v3",
  "migration",
  "step",
  "spec",
]);

function extractStoriesFromMarkdown(
  markdown: string,
  specFile: string,
  ref: string,
): JourneyStory[] {
  const stories: JourneyStory[] = [];
  STORY_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = STORY_RE.exec(markdown)) !== null) {
    const actor = match[1];
    const goalVerb = match[2];
    if (!actor || !goalVerb) continue;
    stories.push({
      ref,
      actor,
      goal: `I ${goalVerb.trim()}`,
      spec_file: specFile,
    });
  }
  return stories;
}

/** Split a slug like 'phase-5b-quote-composition' into normalised tokens. */
function slugTokens(slug: string): string[] {
  return slug
    .toLowerCase()
    .split(/[-_/]+/)
    .map((tok) => tok.trim())
    .filter((tok) => tok.length > 0)
    .filter((tok) => !/^\d+[a-z]?$/.test(tok)) // drop "5", "5b", "12"
    .filter((tok) => !PHASE_SLUG_NOISE.has(tok));
}

/** Split a route like '/quotes/[id]' into lowercase word tokens. */
function routeTokens(route: string): string[] {
  return route
    .toLowerCase()
    .split(/[/[\]]+/)
    .map((tok) => tok.trim())
    .filter((tok) => tok.length > 0);
}

/**
 * Token equality with a light plural-insensitive rule: two tokens match if
 * they are equal, OR one is a length-≥4 prefix of the other (so "quote" and
 * "quotes" match; "q" and "quotes" do not). No stemming beyond this.
 */
function tokensMatch(a: string, b: string): boolean {
  if (a === b) return true;
  const [shorter, longer] = a.length <= b.length ? [a, b] : [b, a];
  if (shorter.length < 4) return false;
  return longer.startsWith(shorter);
}

/**
 * Score how well a spec-directory slug matches a route path.
 * Returns the number of overlapping tokens; 0 means no overlap.
 */
function fuzzyScore(specSlug: string, route: string): number {
  const specToks = slugTokens(specSlug);
  const routeToks = routeTokens(route);
  let overlap = 0;
  for (const routeTok of routeToks) {
    if (specToks.some((specTok) => tokensMatch(specTok, routeTok))) {
      overlap += 1;
    }
  }
  return overlap;
}

/**
 * Find all routes that fuzzy-match the spec slug at the highest-available
 * overlap score. When multiple routes tie (e.g. `/quotes` and `/quotes/[id]`
 * both match on the "quote" token), all are returned so the UI surfaces the
 * story on every candidate node.
 */
function fuzzyMatchRoutes(
  specSlug: string,
  knownRoutes: readonly string[],
): string[] {
  const scored = knownRoutes
    .map((route) => ({ route, score: fuzzyScore(specSlug, route) }))
    .filter((entry) => entry.score > 0);
  if (scored.length === 0) return [];
  const best = Math.max(...scored.map((entry) => entry.score));
  return scored.filter((entry) => entry.score === best).map((entry) => entry.route);
}

function toNodeId(route: string): JourneyNodeId {
  return `app:${route}` as JourneyNodeId;
}

async function listSpecDirs(specsRoot: string): Promise<string[]> {
  const entries = await fs.readdir(specsRoot, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(specsRoot, entry.name));
}

async function listMarkdownFiles(dir: string): Promise<string[]> {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const results: string[] = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isFile() && entry.name.endsWith(".md")) {
      results.push(full);
    } else if (entry.isDirectory()) {
      const nested = await listMarkdownFiles(full);
      results.push(...nested);
    }
  }
  return results;
}

export async function parseSpecs(
  options: ParseSpecsOptions,
): Promise<ParseSpecsResult> {
  const { specsRoot, knownRoutes } = options;

  const storiesByNodeId: Record<string, JourneyStory[]> = {};
  const unbound: JourneyStory[] = [];
  const knownRouteSet = new Set(knownRoutes);

  const specDirs = await listSpecDirs(specsRoot);

  for (const specDir of specDirs) {
    const specSlug = path.basename(specDir);
    const mdFiles = await listMarkdownFiles(specDir);
    if (mdFiles.length === 0) continue;

    for (const mdPath of mdFiles) {
      const raw = await fs.readFile(mdPath, "utf8");
      const parsed = matter(raw);
      const frontmatter = parsed.data as {
        related_routes?: readonly string[];
      };

      // Emit stories with a spec_file path relative to specsRoot so the output
      // is portable across machines/CI and deterministic across runs.
      const specFileRel = path.relative(specsRoot, mdPath);
      const ref = specSlug;
      const stories = extractStoriesFromMarkdown(parsed.content, specFileRel, ref);
      if (stories.length === 0) continue;

      // Priority 1: explicit frontmatter binding.
      const explicitRoutes: string[] = Array.isArray(frontmatter.related_routes)
        ? frontmatter.related_routes.filter((r): r is string => typeof r === "string")
        : [];
      const boundRoutes = explicitRoutes.filter((r) => knownRouteSet.has(r));

      // Priority 2: fuzzy directory-slug match.
      let finalRoutes: string[] = boundRoutes;
      if (finalRoutes.length === 0) {
        finalRoutes = fuzzyMatchRoutes(specSlug, knownRoutes);
      }

      if (finalRoutes.length === 0) {
        unbound.push(...stories);
        continue;
      }

      for (const route of finalRoutes) {
        const nodeId = toNodeId(route);
        const bucket = storiesByNodeId[nodeId] ?? [];
        bucket.push(...stories);
        storiesByNodeId[nodeId] = bucket;
      }
    }
  }

  return { storiesByNodeId, unbound };
}
