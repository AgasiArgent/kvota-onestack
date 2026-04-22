/**
 * parse-roles.ts — extracts the role × route-cluster visibility matrix from
 * `.kiro/steering/access-control.md`.
 *
 * One of three manifest parsers (with parse-routes, parse-specs). Output is a
 * `Record<RoleSlug, Record<ClusterName, boolean>>` consumed by
 * `build-manifest.ts` to populate `JourneyNode.roles`.
 *
 * Parser strategy (no markdown-AST dep — keep script deps lean):
 *   1. Slice the document into line buffers.
 *   2. Extract the `## Visibility Tiers` table → build `role → tier` map.
 *   3. Walk `## Entity-Level Rules` — each `### <Entity>` heading starts a
 *      cluster. The following region is either:
 *        (a) a GFM table with first column `Tier`, second column access spec
 *            for List, or
 *        (b) a narrative line "<Entity> follow the same rules as <Other>."
 *   4. For each (role, cluster) determine `visible = true` unless the relevant
 *      row's access column is "No access" (with or without bold markers).
 *   5. Narrative clusters copy the matching cluster's column wholesale.
 *
 * Cluster names are slugified to lowercase `[a-z0-9_]+` so they match
 * `JourneyNode.cluster` slugs emitted by `parse-routes.ts`.
 */

import { readFile } from "node:fs/promises";
import type { RoleSlug } from "../../src/entities/journey/types";

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/** Lowercase cluster slug, e.g. `customers`, `quotes`, `suppliers`. */
export type ClusterName = string;

/** Per-role visibility flag keyed by cluster slug. */
export type RoleVisibilityMatrix = Record<RoleSlug, Record<ClusterName, boolean>>;

// ---------------------------------------------------------------------------
// Role slug registry
// ---------------------------------------------------------------------------

const ALL_ROLES: readonly RoleSlug[] = [
  "admin",
  "top_manager",
  "head_of_sales",
  "head_of_procurement",
  "head_of_logistics",
  "sales",
  "quote_controller",
  "spec_controller",
  "finance",
  "procurement",
  "procurement_senior",
  "logistics",
  "customs",
];
const ROLE_SET = new Set<string>(ALL_ROLES);

function isRoleSlug(value: string): value is RoleSlug {
  return ROLE_SET.has(value);
}

// ---------------------------------------------------------------------------
// Minimal markdown helpers
// ---------------------------------------------------------------------------

/**
 * Strip GFM bold/italic/code markers from a cell value.
 *
 * Underscore italics (`_foo_`) are only stripped when the underscores sit at a
 * word boundary — this preserves snake_case role slugs like `head_of_procurement`.
 */
function stripInline(raw: string): string {
  return raw
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/(^|[^a-zA-Z0-9_])_([^_\s][^_]*[^_\s]|[^_\s])_(?=[^a-zA-Z0-9_]|$)/g, "$1$2")
    .trim();
}

/** Split a GFM table row `| a | b | c |` into trimmed cells. */
function splitRow(line: string): string[] {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|")) return [];
  return trimmed
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isTableRow(line: string): boolean {
  return /^\s*\|.*\|\s*$/.test(line);
}

function isTableSeparator(line: string): boolean {
  // e.g. |------|------|------|
  return /^\s*\|(\s*:?-+:?\s*\|)+\s*$/.test(line);
}

/**
 * Extract the GFM table that starts at (or after) the given line index.
 * Returns { header, rows, nextIndex } where `nextIndex` is the line just
 * after the table (or -1 if no table found).
 */
function extractTable(
  lines: string[],
  startIndex: number,
): { header: string[]; rows: string[][]; nextIndex: number } | null {
  // Find the first table row at/after startIndex.
  let i = startIndex;
  while (i < lines.length && !isTableRow(lines[i])) i++;
  if (i >= lines.length) return null;

  const headerIdx = i;
  const sepIdx = headerIdx + 1;
  if (sepIdx >= lines.length || !isTableSeparator(lines[sepIdx])) return null;

  const header = splitRow(lines[headerIdx]);
  const rows: string[][] = [];
  let cursor = sepIdx + 1;
  while (cursor < lines.length && isTableRow(lines[cursor])) {
    rows.push(splitRow(lines[cursor]));
    cursor++;
  }
  return { header, rows, nextIndex: cursor };
}

// ---------------------------------------------------------------------------
// Parse visibility tiers
// ---------------------------------------------------------------------------

/**
 * Section marker detection — we key on `## Visibility Tiers` (case-insensitive,
 * leading/trailing whitespace tolerant).
 */
function findHeading(lines: string[], level: number, text: string, from = 0): number {
  const marker = "#".repeat(level) + " ";
  const target = text.toLowerCase();
  for (let i = from; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line.startsWith(marker)) continue;
    if (line.slice(marker.length).toLowerCase().startsWith(target)) return i;
  }
  return -1;
}

function parseTierToRoles(lines: string[]): Map<string, RoleSlug[]> {
  const tierToRoles = new Map<string, RoleSlug[]>();
  const headingIdx = findHeading(lines, 2, "visibility tiers");
  if (headingIdx < 0) return tierToRoles;

  const table = extractTable(lines, headingIdx);
  if (!table) return tierToRoles;

  // Expected columns: Tier | Roles | Scope
  for (const row of table.rows) {
    if (row.length < 2) continue;
    const tier = stripInline(row[0]).toUpperCase();
    if (!tier) continue;
    // Roles column may contain multiple backticked slugs separated by commas.
    const roles: RoleSlug[] = [];
    const rolesRaw = row[1];
    const matches = rolesRaw.matchAll(/`([^`]+)`/g);
    for (const m of matches) {
      const slug = m[1].trim();
      if (isRoleSlug(slug)) roles.push(slug);
    }
    // Fallback: if no backticks (e.g. narrative), split by comma and scan words.
    if (roles.length === 0) {
      const fallback = stripInline(rolesRaw)
        .split(/[,/]/)
        .map((s) => s.trim());
      for (const candidate of fallback) {
        if (isRoleSlug(candidate)) roles.push(candidate);
      }
    }
    if (roles.length > 0) tierToRoles.set(tier, roles);
  }
  return tierToRoles;
}

// ---------------------------------------------------------------------------
// Parse entity-level rules
// ---------------------------------------------------------------------------

/**
 * Each entity section begins at `### <Entity>`. We collect a block from the
 * heading to the next `##`/`###` heading for downstream narrative/table work.
 */
interface EntityBlock {
  readonly name: string;
  readonly cluster: ClusterName;
  readonly startIndex: number;
  readonly endIndex: number; // exclusive
}

function slugify(name: string): ClusterName {
  return name
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function collectEntityBlocks(lines: string[]): EntityBlock[] {
  const entitySectionIdx = findHeading(lines, 2, "entity-level rules");
  if (entitySectionIdx < 0) return [];

  // End at next `## ` heading or EOF.
  let end = lines.length;
  for (let i = entitySectionIdx + 1; i < lines.length; i++) {
    if (/^##\s+\S/.test(lines[i]) && !/^###\s/.test(lines[i])) {
      end = i;
      break;
    }
  }

  const blocks: EntityBlock[] = [];
  for (let i = entitySectionIdx + 1; i < end; i++) {
    const line = lines[i];
    const match = line.match(/^###\s+(.+?)\s*$/);
    if (!match) continue;
    const name = match[1].trim();
    // Find the next ### within the entity section.
    let blockEnd = end;
    for (let j = i + 1; j < end; j++) {
      if (/^###\s+\S/.test(lines[j])) {
        blockEnd = j;
        break;
      }
    }
    blocks.push({
      name,
      cluster: slugify(name),
      startIndex: i,
      endIndex: blockEnd,
    });
  }
  return blocks;
}

/**
 * Decide whether an access cell ("List" column) grants visibility.
 * "No access" (case-insensitive, with or without bold) → false; any other
 * non-empty value → true.
 */
function cellGrantsAccess(raw: string): boolean {
  const normalised = stripInline(raw).toLowerCase();
  if (!normalised) return false;
  return !normalised.includes("no access");
}

/**
 * Parse a single entity-rules table. Returns a partial map of role → visible;
 * roles not mentioned are left undefined for the caller to fill with defaults.
 *
 * Supported first-column shapes (seen in access-control.md):
 *   - Bare tier name:           `OWN`
 *   - Tier name with parenthetical role: `OWN (sales)` or
 *                                        `ASSIGNED_ITEMS (procurement/logistics/customs)`
 *   - Tier name with slash:     `FULL_VIEW_EDIT / FULL_VIEW_READONLY`
 *   - Wildcard tier:            `PROCUREMENT_*`
 *   - Bare role slug:           `head_of_procurement`, `procurement_senior`
 *   - Catch-all:                `All other roles`
 */
function parseEntityTable(
  table: { header: string[]; rows: string[][] },
  tierToRoles: Map<string, RoleSlug[]>,
): {
  explicit: Partial<Record<RoleSlug, boolean>>;
  catchAll: boolean | null;
} {
  const explicit: Partial<Record<RoleSlug, boolean>> = {};
  let catchAll: boolean | null = null;

  // Index of the "List" (or second) column — the visibility decision comes
  // from whether it says "No access".
  const listIdx = findColumnIndex(table.header, "list") ?? 1;

  for (const row of table.rows) {
    if (row.length < 2) continue;
    const first = stripInline(row[0]);
    const listCell = row[listIdx] ?? "";
    const grants = cellGrantsAccess(listCell);

    // Catch-all row.
    if (/^all other roles$/i.test(first)) {
      catchAll = grants;
      continue;
    }

    const targetRoles = resolveFirstColumnToRoles(first, tierToRoles);
    for (const role of targetRoles) {
      // Do not overwrite a prior explicit `false` with `true` for the same role
      // — but within one table this shouldn't happen; keep first-write semantics.
      if (explicit[role] === undefined) explicit[role] = grants;
    }
  }
  return { explicit, catchAll };
}

function findColumnIndex(header: string[], name: string): number | null {
  const target = name.toLowerCase();
  for (let i = 0; i < header.length; i++) {
    if (stripInline(header[i]).toLowerCase() === target) return i;
  }
  return null;
}

function resolveFirstColumnToRoles(
  cell: string,
  tierToRoles: Map<string, RoleSlug[]>,
): RoleSlug[] {
  const roles = new Set<RoleSlug>();

  // Strip the parenthetical suffix for tier matching, but also mine it for
  // role names — the parenthetical often lists the concrete roles a tier maps
  // to, which is what we actually want.
  const parenMatches = [...cell.matchAll(/\(([^)]+)\)/g)];
  for (const m of parenMatches) {
    const inner = m[1];
    for (const candidate of inner.split(/[,/]/).map((s) => s.trim())) {
      if (isRoleSlug(candidate)) roles.add(candidate);
    }
  }

  // Match bare role slugs anywhere in the cell.
  const tokenMatches = cell.matchAll(/[a-z_][a-z0-9_]+/g);
  for (const m of tokenMatches) {
    if (isRoleSlug(m[0])) roles.add(m[0]);
  }

  // Remove parens before tier lookup.
  const stripped = cell.replace(/\([^)]*\)/g, "").trim();

  // A cell may contain several slash-separated tiers.
  const tierCandidates = stripped
    .split(/\s*\/\s*/)
    .map((s) => s.toUpperCase().trim())
    .filter(Boolean);

  for (const candidate of tierCandidates) {
    // Wildcard tier: `PROCUREMENT_*` — expand to every tier starting with
    // `PROCUREMENT_`.
    if (candidate.endsWith("*")) {
      const prefix = candidate.slice(0, -1);
      for (const [tier, tierRoles] of tierToRoles.entries()) {
        if (tier.startsWith(prefix)) for (const r of tierRoles) roles.add(r);
      }
      continue;
    }
    const tierRoles = tierToRoles.get(candidate);
    if (tierRoles) for (const r of tierRoles) roles.add(r);
  }

  return [...roles];
}

/**
 * Parse narrative lines describing "this entity follows the visibility of X".
 * Supported phrasings (case-insensitive), mirroring the shapes used in
 * `access-control.md`:
 *   - "Specifications follow the same rules as quotes."
 *   - "Follow the same rules as specs/quotes." (slash-separated alternatives)
 *   - "Follow customer visibility."
 *   - "Follows deal visibility."
 *
 * Returns an ordered list of candidate entity aliases. The caller tries them
 * in order and picks the first that maps to a resolved cluster.
 */
function detectNarrativeAliases(
  lines: string[],
  startIndex: number,
  endIndex: number,
): string[] {
  for (let i = startIndex; i < endIndex; i++) {
    const line = lines[i];
    // Strip bold markers so `**Follow customer visibility.**` also matches.
    const normalised = line.replace(/\*\*/g, "");
    // "same rules as X" or "same rules as X/Y/Z"
    let m = normalised.match(/same rules as (?:the\s+)?([a-z_/]+)/i);
    if (m) return splitAliases(m[1]);
    // "follow(s) X visibility"
    m = normalised.match(/follows?\s+(?:the\s+)?([a-z_]+)\s+visibility/i);
    if (m) return splitAliases(m[1]);
  }
  return [];
}

function splitAliases(raw: string): string[] {
  return raw
    .toLowerCase()
    .split("/")
    .map((s) => s.trim())
    .filter(Boolean)
    .flatMap(expandEntityAlias);
}

/**
 * Return variants of an entity word to try against cluster slugs.
 * Covers plural/singular and common abbreviations used in `access-control.md`
 * prose vs plural headings.
 */
function expandEntityAlias(word: string): string[] {
  const variants = new Set<string>();
  variants.add(word);
  variants.add(word.endsWith("s") ? word : word + "s");
  // Domain abbreviations.
  if (word === "spec" || word === "specs") variants.add("specifications");
  if (word === "deal" || word === "deals") variants.add("deals");
  if (word === "customer" || word === "customers") variants.add("customers");
  if (word === "quote" || word === "quotes") variants.add("quotes");
  if (word === "supplier" || word === "suppliers") variants.add("suppliers");
  return [...variants];
}

// ---------------------------------------------------------------------------
// Orchestrator
// ---------------------------------------------------------------------------

/**
 * Parse `access-control.md` and return the role × cluster visibility matrix.
 *
 * @param markdownPath Absolute path to the access-control markdown file.
 */
export async function parseRoles(markdownPath: string): Promise<RoleVisibilityMatrix> {
  const raw = await readFile(markdownPath, "utf8");
  const lines = raw.split(/\r?\n/);

  const tierToRoles = parseTierToRoles(lines);
  const blocks = collectEntityBlocks(lines);

  // First pass: parse every table-backed block. Narrative blocks recorded for
  // resolution in the second pass.
  type ClusterVisibility = Partial<Record<RoleSlug, boolean>> & { __catchAll?: boolean | null };

  const clusterToVisibility = new Map<ClusterName, ClusterVisibility>();
  const aliasQueue: Array<{ cluster: ClusterName; aliasCandidates: ClusterName[] }> = [];

  for (const block of blocks) {
    const table = extractTable(lines, block.startIndex + 1);
    if (table && table.nextIndex <= block.endIndex) {
      const { explicit, catchAll } = parseEntityTable(table, tierToRoles);
      const vis: ClusterVisibility = { ...explicit, __catchAll: catchAll };
      clusterToVisibility.set(block.cluster, vis);
      continue;
    }
    const aliases = detectNarrativeAliases(lines, block.startIndex + 1, block.endIndex);
    if (aliases.length > 0) {
      aliasQueue.push({
        cluster: block.cluster,
        aliasCandidates: aliases.map(slugify),
      });
    }
    // Else: entity declared but no parsable rules — skip silently.
  }

  // Second pass: resolve aliases. Aliases may chain (Payments → Deals →
  // Specifications → Quotes), so iterate until the set of unresolved aliases
  // stops shrinking.
  let pending = [...aliasQueue];
  for (let guard = 0; guard < 10 && pending.length > 0; guard++) {
    const next: typeof pending = [];
    let resolvedThisPass = 0;
    for (const item of pending) {
      const source = item.aliasCandidates
        .map((cluster) => clusterToVisibility.get(cluster))
        .find((v): v is ClusterVisibility => v !== undefined);
      if (source) {
        clusterToVisibility.set(item.cluster, { ...source });
        resolvedThisPass++;
      } else {
        next.push(item);
      }
    }
    if (resolvedThisPass === 0) break;
    pending = next;
  }

  // Finalise: fill in missing roles per cluster using catch-all (or false).
  const matrix: RoleVisibilityMatrix = {} as RoleVisibilityMatrix;
  for (const role of ALL_ROLES) {
    matrix[role] = {};
  }

  for (const [cluster, vis] of clusterToVisibility.entries()) {
    const fallback = vis.__catchAll ?? false;
    for (const role of ALL_ROLES) {
      const explicit = vis[role];
      matrix[role][cluster] = explicit === undefined ? fallback : explicit;
    }
  }

  return matrix;
}
