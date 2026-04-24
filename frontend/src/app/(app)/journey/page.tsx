/**
 * `/journey` page — three-pane Customer Journey Map shell.
 *
 * - Auth guard is inherited from `(app)/layout.tsx` (redirects to /login).
 * - Server Component: reads the build-time manifest from disk and parses
 *   URL search params into `JourneyUrlState`, then hands both to a client
 *   component that owns canvas/drawer/sidebar rendering.
 *
 * Reqs: 3.1, 3.2, 3.10, 3.11
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import type { JourneyManifest, RoleSlug } from "@/entities/journey";
import { getSessionUser } from "@/entities/user/server";
import {
  JourneyShell,
  decodeFromSearchParams,
  type JourneyUrlState,
} from "@/features/journey";

interface JourneyPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

async function loadManifest(): Promise<JourneyManifest> {
  const manifestPath = path.join(
    process.cwd(),
    "public",
    "journey-manifest.json",
  );
  const raw = await fs.readFile(manifestPath, "utf8");
  return JSON.parse(raw) as JourneyManifest;
}

function paramsToURLSearchParams(
  params: Record<string, string | string[] | undefined>,
): URLSearchParams {
  const urlParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === "string") {
      urlParams.set(key, value);
    } else if (Array.isArray(value) && value.length > 0) {
      // Next.js collapses duplicate keys into string[]; the journey URL
      // schema only uses scalar values, so we take the first occurrence.
      urlParams.set(key, value[0]);
    }
  }
  return urlParams;
}

export default async function JourneyPage({ searchParams }: JourneyPageProps) {
  const params = await searchParams;
  const [manifest, user] = await Promise.all([
    loadManifest(),
    getSessionUser(),
  ]);
  const initialUrlState: JourneyUrlState = decodeFromSearchParams(
    paramsToURLSearchParams(params),
  );

  // Narrow SessionUser.roles (string[]) down to the RoleSlug union.
  // Unknown slugs are dropped — downstream access helpers assume the union.
  const userRoles = (user?.roles ?? []).filter((slug): slug is RoleSlug =>
    [
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
    ].includes(slug),
  );

  return (
    <JourneyShell
      manifest={manifest}
      initialUrlState={initialUrlState}
      userId={user?.id ?? null}
      userRoles={userRoles}
    />
  );
}
