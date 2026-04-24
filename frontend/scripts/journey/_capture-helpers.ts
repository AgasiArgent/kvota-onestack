/**
 * Pure helpers for the journey screenshot capture script.
 *
 * Extracted from `capture-screenshots.ts` so they can be unit-tested without
 * spinning up Playwright or hitting Supabase Storage.
 *
 * Shape of the Playwright webhook payload matches
 * `api/models/journey.py::PlaywrightWebhookPinUpdate`:
 *
 *   { pin_id: string, bbox: { rel_x, rel_y, rel_width, rel_height } | null }
 *
 * A `null` bbox flips `selector_broken=true` on the server (Req 10.8 — the
 * spec's flat shape is materialised server-side; the wire shape stays nested
 * to keep the payload unambiguous when bbox is absent).
 *
 * Requirements: §10.2, §10.5, §10.6, §10.8, §10.9.
 */

/** Env vars that MUST be present for a non-dry-run capture. */
export const REQUIRED_ENV = [
  "SUPABASE_URL",
  "SUPABASE_SERVICE_ROLE_KEY",
  "JOURNEY_WEBHOOK_TOKEN",
  "JOURNEY_BASE_URL",
  "JOURNEY_TEST_USERS_PASSWORD",
] as const;

export type RequiredEnvKey = (typeof REQUIRED_ENV)[number];

export interface CaptureEnv {
  readonly SUPABASE_URL: string;
  readonly SUPABASE_SERVICE_ROLE_KEY: string;
  readonly JOURNEY_WEBHOOK_TOKEN: string;
  readonly JOURNEY_BASE_URL: string;
  readonly JOURNEY_TEST_USERS_PASSWORD: string;
}

/**
 * Fail-fast env reader. Throws with a message listing every missing key.
 *
 * Accepts any `Record<string, string | undefined>` so tests can pass a plain
 * literal without forging a full `NodeJS.ProcessEnv` shape (NODE_ENV etc.).
 */
export function requireEnv(
  source: Record<string, string | undefined> = process.env as Record<
    string,
    string | undefined
  >,
): CaptureEnv {
  const missing = REQUIRED_ENV.filter((k) => !source[k] || source[k] === "");
  if (missing.length > 0) {
    throw new Error(
      `Missing required env vars: ${missing.join(", ")}. ` +
        `All of [${REQUIRED_ENV.join(", ")}] must be set.`,
    );
  }
  // Non-null assertions are safe after the filter above.
  return {
    SUPABASE_URL: source.SUPABASE_URL!,
    SUPABASE_SERVICE_ROLE_KEY: source.SUPABASE_SERVICE_ROLE_KEY!,
    JOURNEY_WEBHOOK_TOKEN: source.JOURNEY_WEBHOOK_TOKEN!,
    JOURNEY_BASE_URL: source.JOURNEY_BASE_URL!,
    JOURNEY_TEST_USERS_PASSWORD: source.JOURNEY_TEST_USERS_PASSWORD!,
  };
}

// ---------------------------------------------------------------------------
// Screenshot path — Req 10.5
// ---------------------------------------------------------------------------

/**
 * Turn a node_id into a filesystem-safe segment.
 *
 * Rules (match Req 10.5):
 *   - Strip the `app:` URL-scheme prefix if present.
 *   - Replace `/` with `_` so the whole thing fits in a single path segment
 *     under the `{role}/{node_id_safe}/` prefix.
 *   - Replace any other non-alphanum character (brackets, spaces, dashes)
 *     with `_` to avoid shell / URL escaping edge-cases.
 */
export function nodeIdToSafeSegment(nodeId: string): string {
  const stripped = nodeId.startsWith("app:") ? nodeId.slice("app:".length) : nodeId;
  return stripped
    .replace(/^\//, "") // drop leading slash after stripping app:
    .replace(/[^a-zA-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

/**
 * Build the storage path for a (role, node, date) capture.
 * Format: `{role}/{node_id_safe}/{YYYY-MM-DD}.png`.
 */
export function buildScreenshotPath(
  role: string,
  nodeId: string,
  isoDate: string,
): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) {
    throw new Error(
      `buildScreenshotPath: isoDate must be YYYY-MM-DD, got "${isoDate}"`,
    );
  }
  return `${role}/${nodeIdToSafeSegment(nodeId)}/${isoDate}.png`;
}

// ---------------------------------------------------------------------------
// Bbox resolution — Req 10.8
// ---------------------------------------------------------------------------

export interface Viewport {
  readonly width: number;
  readonly height: number;
}

export interface PixelBbox {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface WebhookBbox {
  readonly rel_x: number;
  readonly rel_y: number;
  readonly rel_width: number;
  readonly rel_height: number;
}

export interface WebhookPinUpdate {
  readonly pin_id: string;
  readonly bbox: WebhookBbox | null;
}

/**
 * Convert a Playwright `boundingBox()` result into a webhook payload entry.
 *
 * `null` bbox (selector did not resolve) → `{ pin_id, bbox: null }` which the
 * server interprets as `selector_broken=true` (see `journey_service`).
 */
export function buildBboxUpdate(
  pinId: string,
  bbox: PixelBbox | null,
  viewport: Viewport,
): WebhookPinUpdate {
  if (bbox === null) {
    return { pin_id: pinId, bbox: null };
  }
  if (viewport.width <= 0 || viewport.height <= 0) {
    throw new Error(
      `buildBboxUpdate: viewport must have positive dimensions, got ` +
        `${viewport.width}×${viewport.height}`,
    );
  }
  return {
    pin_id: pinId,
    bbox: {
      rel_x: bbox.x / viewport.width,
      rel_y: bbox.y / viewport.height,
      rel_width: bbox.width / viewport.width,
      rel_height: bbox.height / viewport.height,
    },
  };
}

// ---------------------------------------------------------------------------
// Dynamic route substitution
// ---------------------------------------------------------------------------

export type FixtureMap = Record<string, string>;

/**
 * Substitute `[param]` placeholders in a Next.js dynamic route using the
 * curated fixture map (keyed by node_id, e.g. `"app:/quotes/[id]"`).
 *
 * Returns `null` when the route contains any unfilled placeholder — the
 * caller should skip dynamic routes without a fixture rather than hitting
 * a 404 / empty page (Req 10.5 — retention keys depend on stable paths).
 */
export function substituteDynamicRoute(
  nodeId: string,
  route: string,
  fixtures: FixtureMap,
): string | null {
  if (!route.includes("[")) {
    return route;
  }
  const replacement = fixtures[nodeId];
  if (!replacement || replacement.trim() === "") {
    return null;
  }
  // Replace any `[param]` or `[...param]` with the fixture value. A fixture
  // that itself contains `/` is allowed (e.g. `"abc/def"`) so catch-all
  // segments work.
  const substituted = route.replace(/\[\.{0,3}[^\]]+\]/g, replacement);
  if (substituted.includes("[")) {
    // Defensive: if the replacement leaves unresolved placeholders, drop it.
    return null;
  }
  return substituted;
}

// ---------------------------------------------------------------------------
// Retention — Req 10.6
// ---------------------------------------------------------------------------

export interface StoredFile {
  readonly path: string;
  /** YYYY-MM-DD parsed out of the filename or last-modified timestamp. */
  readonly date: string;
}

/**
 * Given the list of screenshots stored under a `(role, node)` prefix, return
 * the paths that should be deleted to retain only the N newest.
 *
 * Sort order: ISO YYYY-MM-DD compares correctly as a string, so no Date
 * parsing is needed. Ties (same date) are broken by path string to keep the
 * result deterministic across runs.
 */
export function pruneRetainedFiles(
  files: readonly StoredFile[],
  keep = 2,
): readonly string[] {
  if (keep < 0) {
    throw new Error(`pruneRetainedFiles: keep must be >=0, got ${keep}`);
  }
  const sorted = [...files].sort((a, b) => {
    if (a.date === b.date) return a.path < b.path ? 1 : -1;
    return a.date < b.date ? 1 : -1; // newest first
  });
  return sorted.slice(keep).map((f) => f.path);
}

// ---------------------------------------------------------------------------
// Dry-run summary
// ---------------------------------------------------------------------------

export interface DryRunSummaryInput {
  readonly roles: readonly string[];
  readonly nodesVisited: number;
  readonly pinsResolved: number;
  readonly pinsBroken: number;
}

/**
 * Stable textual summary for `--dry-run=1` mode.
 * Kept as a pure function so a snapshot test can pin the output shape.
 */
export function dryRunSummary(input: DryRunSummaryInput): string {
  const roleList = [...input.roles].sort().join(", ") || "(none)";
  return [
    "[journey-capture] dry-run summary",
    `  roles: ${roleList}`,
    `  nodes visited: ${input.nodesVisited}`,
    `  pins resolved: ${input.pinsResolved}`,
    `  pins broken:   ${input.pinsBroken}`,
  ].join("\n");
}

// ---------------------------------------------------------------------------
// Manifest helpers
// ---------------------------------------------------------------------------

export interface ManifestNodeLite {
  readonly node_id: string;
  readonly route: string;
  readonly roles: readonly string[];
}

export interface ManifestLite {
  readonly nodes: readonly ManifestNodeLite[];
}

/**
 * Collect the deduplicated set of roles referenced anywhere in the manifest.
 * Sorted for deterministic iteration (makes retention traces diff-stable).
 */
export function listRolesFromManifest(manifest: ManifestLite): readonly string[] {
  const roles = new Set<string>();
  for (const node of manifest.nodes) {
    for (const role of node.roles) {
      if (role) roles.add(role);
    }
  }
  return [...roles].sort();
}

/** Filter manifest nodes that should be visited for a given role. */
export function nodesForRole(
  manifest: ManifestLite,
  role: string,
): readonly ManifestNodeLite[] {
  return manifest.nodes.filter((n) => n.roles.includes(role));
}
