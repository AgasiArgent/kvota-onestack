#!/usr/bin/env tsx
/**
 * Journey screenshot capture — Playwright pipeline (Task 26).
 *
 * Replaces the Task 25 skeleton with the real nightly capture loop:
 *   1. Load the manifest produced by `npm run journey:build`.
 *   2. For each role referenced in the manifest:
 *        a. Sign in to Supabase as `qa-{role}@kvotaflow.ru` using the shared
 *           staging password (GitHub secret JOURNEY_TEST_USERS_PASSWORD).
 *        b. Visit every node the role can see:
 *             - navigate to JOURNEY_BASE_URL + route (dynamic segments
 *               substituted from capture-fixtures.json, missing fixture
 *               → skip with a warning),
 *             - upload a viewport PNG to
 *               `journey-screenshots/{role}/{node_id_safe}/{YYYY-MM-DD}.png`,
 *             - for each pin attached to the node, resolve
 *               `page.locator(selector).boundingBox()` and collect a
 *               webhook entry (`{pin_id, bbox: {...} | null}`).
 *        c. Prune older captures so only 2 files per (role, node) remain.
 *   3. POST the full batch to `${JOURNEY_BASE_URL}/api/journey/playwright-webhook`
 *      with `X-Journey-Webhook-Token: ${JOURNEY_WEBHOOK_TOKEN}`.
 *
 * Exit codes:
 *   0 — success (including `--dry-run=1`).
 *   1 — capture / webhook failure (non-2xx response, unhandled throw).
 *   2 — configuration error (missing env, manifest unreadable).
 *
 * Requirements: §10.2, §10.5, §10.6, §10.8, §10.9 of
 * `.kiro/specs/customer-journey-map/requirements.md`.
 */
import { promises as fs } from "node:fs";
import path from "node:path";
import { parseArgs } from "node:util";

import { createClient } from "@supabase/supabase-js";
// The supabase-js generic is parameterised on <Database, SchemaName>. We use
// a loose alias so we don't have to wire the generated kvota types through
// this standalone script.
type SupabaseClient = ReturnType<typeof createClient>;
import { chromium, type Browser, type BrowserContext, type Page } from "playwright";

import {
  buildBboxUpdate,
  buildScreenshotPath,
  dryRunSummary,
  listRolesFromManifest,
  nodeIdToSafeSegment,
  nodesForRole,
  pruneRetainedFiles,
  requireEnv,
  substituteDynamicRoute,
  type CaptureEnv,
  type FixtureMap,
  type ManifestLite,
  type ManifestNodeLite,
  type StoredFile,
  type Viewport,
  type WebhookPinUpdate,
} from "./_capture-helpers";

const VIEWPORT: Viewport = { width: 1280, height: 720 };
const STORAGE_BUCKET = "journey-screenshots";
const WEBHOOK_PATH = "/api/journey/playwright-webhook";
const RETENTION_KEEP = 2;

const MANIFEST_PATH = path.resolve(
  process.cwd(),
  "public",
  "journey-manifest.json",
);
const FIXTURES_PATH = path.resolve(
  process.cwd(),
  "scripts",
  "journey",
  "capture-fixtures.json",
);

// ---------------------------------------------------------------------------
// Types — only what we actually touch from supabase / the pin rows
// ---------------------------------------------------------------------------

interface JourneyPinRow {
  readonly id: string;
  readonly node_id: string;
  readonly selector: string;
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const { values } = parseArgs({
    options: { "dry-run": { type: "string", default: "0" } },
    strict: false,
  });
  const dryRun = values["dry-run"] === "1";

  console.log(`[journey-capture] starting (dry-run=${dryRun})`);

  let env: CaptureEnv;
  try {
    env = requireEnv();
  } catch (err) {
    console.error(`[journey-capture] config error: ${(err as Error).message}`);
    process.exit(2);
  }

  const manifest = await loadManifest();
  const fixtures = await loadFixtures();
  const roles = listRolesFromManifest(manifest);

  if (dryRun) {
    const counts = summariseDryRun(manifest, fixtures, roles);
    console.log(
      dryRunSummary({
        roles,
        nodesVisited: counts.nodesVisited,
        pinsResolved: 0, // dry-run does no browser work
        pinsBroken: 0,
      }),
    );
    console.log(`[journey-capture] dry-run: env validated, exiting 0`);
    process.exit(0);
  }

  // `db.schema` scopes all `.from()` queries to the kvota schema without
  // needing the generated kvota Database type. Storage calls are schema-
  // agnostic so the setting is effectively scoped to `.from("journey_pins")`.
  const sb: SupabaseClient = createClient(
    env.SUPABASE_URL,
    env.SUPABASE_SERVICE_ROLE_KEY,
    {
      auth: { persistSession: false, autoRefreshToken: false },
      db: { schema: "kvota" },
    },
    // Cast: the generic default is "public" but we run with "kvota" at
    // runtime — no type-safety cost since JourneyPinRow is checked manually.
  ) as unknown as SupabaseClient;

  const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
  const allUpdates: WebhookPinUpdate[] = [];

  const browser = await chromium.launch({ headless: true });
  try {
    for (const role of roles) {
      const roleUpdates = await captureForRole({
        role,
        manifest,
        fixtures,
        browser,
        sb,
        env,
        today,
      });
      allUpdates.push(...roleUpdates);
    }
  } finally {
    await browser.close();
  }

  if (allUpdates.length === 0) {
    console.warn(
      `[journey-capture] no pin updates collected — skipping webhook POST`,
    );
    process.exit(0);
  }

  await postWebhook(env, allUpdates);
  const resolved = allUpdates.filter((u) => u.bbox !== null).length;
  const broken = allUpdates.length - resolved;
  console.log(
    `[journey-capture] done — ${allUpdates.length} updates (` +
      `${resolved} resolved, ${broken} broken)`,
  );
}

// ---------------------------------------------------------------------------
// Manifest + fixtures
// ---------------------------------------------------------------------------

async function loadManifest(): Promise<ManifestLite> {
  try {
    const raw = await fs.readFile(MANIFEST_PATH, "utf8");
    const parsed = JSON.parse(raw) as ManifestLite;
    if (!parsed.nodes || !Array.isArray(parsed.nodes)) {
      throw new Error("manifest.nodes missing or not an array");
    }
    return parsed;
  } catch (err) {
    console.error(
      `[journey-capture] failed to read manifest at ${MANIFEST_PATH}: ` +
        (err as Error).message,
    );
    process.exit(2);
  }
}

async function loadFixtures(): Promise<FixtureMap> {
  try {
    const raw = await fs.readFile(FIXTURES_PATH, "utf8");
    const parsed = JSON.parse(raw) as { fixtures?: FixtureMap };
    return parsed.fixtures ?? {};
  } catch {
    // Fixtures are optional; an empty map is fine (dynamic routes skipped).
    return {};
  }
}

function summariseDryRun(
  manifest: ManifestLite,
  fixtures: FixtureMap,
  roles: readonly string[],
): { nodesVisited: number } {
  let nodesVisited = 0;
  for (const role of roles) {
    for (const node of nodesForRole(manifest, role)) {
      if (substituteDynamicRoute(node.node_id, node.route, fixtures) !== null) {
        nodesVisited += 1;
      }
    }
  }
  return { nodesVisited };
}

// ---------------------------------------------------------------------------
// Per-role capture
// ---------------------------------------------------------------------------

interface CaptureForRoleArgs {
  role: string;
  manifest: ManifestLite;
  fixtures: FixtureMap;
  browser: Browser;
  sb: SupabaseClient;
  env: CaptureEnv;
  today: string;
}

async function captureForRole(args: CaptureForRoleArgs): Promise<WebhookPinUpdate[]> {
  const { role, manifest, fixtures, browser, sb, env, today } = args;
  const email = `qa-${role}@kvotaflow.ru`;
  console.log(`[journey-capture] role=${role} email=${email}`);

  const session = await signInAsRole(sb, email, env.JOURNEY_TEST_USERS_PASSWORD);
  if (!session) {
    console.warn(
      `[journey-capture] role=${role}: sign-in failed, skipping role`,
    );
    return [];
  }

  const context = await browser.newContext({ viewport: VIEWPORT });
  await seedSupabaseAuthCookie(context, env.JOURNEY_BASE_URL, session);
  const page = await context.newPage();

  const updates: WebhookPinUpdate[] = [];
  try {
    for (const node of nodesForRole(manifest, role)) {
      const url = resolveNodeUrl(node, fixtures, env.JOURNEY_BASE_URL);
      if (!url) {
        console.log(
          `[journey-capture] role=${role} skip=${node.node_id} (no fixture for dynamic route)`,
        );
        continue;
      }

      try {
        const pinUpdates = await captureNode({
          role,
          node,
          url,
          page,
          sb,
          today,
        });
        updates.push(...pinUpdates);
      } catch (err) {
        // Single-node failure must not abort the whole role.
        console.warn(
          `[journey-capture] role=${role} node=${node.node_id} error: ` +
            (err as Error).message,
        );
      }
    }

    // Retention: prune older screenshots per (role, node). Best-effort.
    for (const node of nodesForRole(manifest, role)) {
      try {
        await pruneRoleNode(sb, role, node.node_id);
      } catch (err) {
        console.warn(
          `[journey-capture] retention failed for role=${role} node=${node.node_id}: ` +
            (err as Error).message,
        );
      }
    }
  } finally {
    await context.close();
  }

  return updates;
}

// ---------------------------------------------------------------------------
// Per-node capture
// ---------------------------------------------------------------------------

interface CaptureNodeArgs {
  role: string;
  node: ManifestNodeLite;
  url: string;
  page: Page;
  sb: SupabaseClient;
  today: string;
}

async function captureNode(args: CaptureNodeArgs): Promise<WebhookPinUpdate[]> {
  const { role, node, url, page, sb, today } = args;
  await page.goto(url, { waitUntil: "networkidle", timeout: 30_000 });

  // Screenshot — viewport only (not full page) so pin coordinates map to the
  // same visible region the user sees when /journey renders the overlay.
  const png = await page.screenshot({ type: "png", fullPage: false });
  const storagePath = buildScreenshotPath(role, node.node_id, today);

  const { error: uploadErr } = await sb.storage
    .from(STORAGE_BUCKET)
    .upload(storagePath, png, {
      contentType: "image/png",
      upsert: true,
    });
  if (uploadErr) {
    throw new Error(`storage upload failed: ${uploadErr.message}`);
  }

  // Fetch the pins attached to this node and resolve each selector.
  const { data: pins, error: pinsErr } = await sb
    .from("journey_pins")
    .select("id, node_id, selector")
    .eq("node_id", node.node_id)
    .returns<JourneyPinRow[]>();
  if (pinsErr) {
    throw new Error(`fetch pins failed: ${pinsErr.message}`);
  }

  const updates: WebhookPinUpdate[] = [];
  for (const pin of pins ?? []) {
    let box: { x: number; y: number; width: number; height: number } | null = null;
    try {
      box = await page.locator(pin.selector).first().boundingBox({ timeout: 2_000 });
    } catch {
      box = null;
    }
    updates.push(buildBboxUpdate(pin.id, box, VIEWPORT));
  }

  console.log(
    `[journey-capture] role=${role} node=${node.node_id} pins=${updates.length}`,
  );
  return updates;
}

// ---------------------------------------------------------------------------
// Retention (Req 10.6)
// ---------------------------------------------------------------------------

async function pruneRoleNode(
  sb: SupabaseClient,
  role: string,
  nodeId: string,
): Promise<void> {
  const prefix = `${role}/${nodeIdToSafeSegment(nodeId)}`;
  const { data: files, error } = await sb.storage
    .from(STORAGE_BUCKET)
    .list(prefix, { limit: 100, sortBy: { column: "name", order: "desc" } });
  if (error) {
    throw new Error(`list failed: ${error.message}`);
  }
  if (!files || files.length === 0) return;

  const stored: StoredFile[] = files
    .filter((f) => f.name.endsWith(".png"))
    .map((f) => ({
      path: `${prefix}/${f.name}`,
      // Filename is `YYYY-MM-DD.png` — pull the prefix before `.png`.
      date: f.name.slice(0, 10),
    }));

  const toDelete = pruneRetainedFiles(stored, RETENTION_KEEP);
  if (toDelete.length === 0) return;

  const { error: delErr } = await sb.storage
    .from(STORAGE_BUCKET)
    .remove([...toDelete]);
  if (delErr) {
    throw new Error(`delete failed: ${delErr.message}`);
  }
}

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

interface Session {
  readonly access_token: string;
  readonly refresh_token: string;
}

async function signInAsRole(
  sb: SupabaseClient,
  email: string,
  password: string,
): Promise<Session | null> {
  const { data, error } = await sb.auth.signInWithPassword({ email, password });
  if (error || !data.session) {
    console.warn(
      `[journey-capture] sign-in failed for ${email}: ` +
        (error?.message ?? "no session returned"),
    );
    return null;
  }
  return {
    access_token: data.session.access_token,
    refresh_token: data.session.refresh_token,
  };
}

/**
 * Seed the browser context with the Supabase auth cookie used by the
 * `@supabase/ssr` client on the Next.js side. The cookie name follows the
 * pattern `sb-{project-ref}-auth-token` where `project-ref` is the subdomain
 * of SUPABASE_URL. Value is a JSON-encoded session tuple.
 */
async function seedSupabaseAuthCookie(
  context: BrowserContext,
  baseUrl: string,
  session: Session,
): Promise<void> {
  const { hostname } = new URL(baseUrl);
  // project-ref appears only when SUPABASE_URL is a real supabase.co host;
  // on a self-hosted staging URL we fall back to the host name — the cookie
  // still rides the same domain as `baseUrl`, so SSR picks it up.
  const cookieName = `sb-staging-auth-token`;
  const cookieValue = JSON.stringify([
    session.access_token,
    session.refresh_token,
  ]);

  await context.addCookies([
    {
      name: cookieName,
      value: encodeURIComponent(cookieValue),
      domain: hostname,
      path: "/",
      httpOnly: false,
      secure: hostname !== "localhost",
      sameSite: "Lax",
    },
  ]);
}

function resolveNodeUrl(
  node: ManifestNodeLite,
  fixtures: FixtureMap,
  baseUrl: string,
): string | null {
  const route = substituteDynamicRoute(node.node_id, node.route, fixtures);
  if (!route) return null;
  const joined = route.startsWith("/") ? route : `/${route}`;
  return baseUrl.replace(/\/$/, "") + joined;
}

// ---------------------------------------------------------------------------
// Webhook
// ---------------------------------------------------------------------------

async function postWebhook(
  env: CaptureEnv,
  updates: readonly WebhookPinUpdate[],
): Promise<void> {
  const url = env.JOURNEY_BASE_URL.replace(/\/$/, "") + WEBHOOK_PATH;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Journey-Webhook-Token": env.JOURNEY_WEBHOOK_TOKEN,
    },
    body: JSON.stringify({ updates }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    console.error(
      `[journey-capture] webhook POST ${url} → ${res.status}: ${body.slice(0, 500)}`,
    );
    process.exit(1);
  }
}

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

main().catch((err: unknown) => {
  console.error("[journey-capture] unhandled error:", err);
  process.exit(1);
});
