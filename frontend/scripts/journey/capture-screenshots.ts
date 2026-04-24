#!/usr/bin/env tsx
/**
 * Journey screenshot capture — Playwright pipeline entry point.
 *
 * Task 25 (this file): skeleton with --dry-run support and env validation.
 * Task 26 will ship the real capture/bbox/webhook loop that:
 *   - logs in as each `qa-{role}@kvotaflow.ru` test user
 *   - iterates manifest.nodes × roles visible to the role
 *   - uploads screenshots to the `journey-screenshots` bucket
 *   - measures per-pin bbox rects and POSTs them to
 *     `POST /api/journey/playwright-webhook` with X-Journey-Webhook-Token.
 *
 * Requirements: §10.1–§10.9 of `.kiro/specs/customer-journey-map/requirements.md`.
 */
import { parseArgs } from "node:util";

const REQUIRED_ENV = [
  "SUPABASE_URL",
  "SUPABASE_SERVICE_ROLE_KEY",
  "JOURNEY_WEBHOOK_TOKEN",
  "JOURNEY_BASE_URL",
  "JOURNEY_TEST_USERS_PASSWORD",
] as const;

async function main(): Promise<void> {
  const { values } = parseArgs({
    options: {
      "dry-run": { type: "string", default: "0" },
    },
    strict: false,
  });

  const dryRun = values["dry-run"] === "1";
  console.log(`[journey-capture] starting (dry-run=${dryRun})`);

  const missing = REQUIRED_ENV.filter((k) => !process.env[k]);
  if (missing.length > 0) {
    console.error(
      `[journey-capture] missing env vars: ${missing.join(", ")}`,
    );
    process.exit(1);
  }

  if (dryRun) {
    console.log("[journey-capture] dry-run: env validated, exiting 0");
    process.exit(0);
  }

  console.log(
    "[journey-capture] Task 26 will ship the real capture loop; this is a skeleton.",
  );
  process.exit(0);
}

main().catch((err: unknown) => {
  console.error("[journey-capture] unhandled error:", err);
  process.exit(1);
});
