/**
 * `/journey/flows/[slug]` — dedicated flow runner page (Req 18.4).
 *
 * - Auth guard is inherited from `(app)/layout.tsx` (redirects to /login).
 * - Server Component: loads the build-time manifest from disk so the client
 *   `<FlowView />` can flag steps that reference node_ids no longer present
 *   (Req 18.10). Flow data itself is fetched client-side via the `useFlows`
 *   TanStack hook — the same cache entry the sidebar uses in Task 28.
 *
 * Reqs: 18.3, 18.4, 18.5, 18.6, 18.7, 18.9, 18.10, 18.11
 */

import { promises as fs } from "node:fs";
import path from "node:path";
import type { JourneyManifest } from "@/entities/journey";
import { FlowView } from "@/features/journey/ui/flows/flow-view";

interface FlowRunnerPageProps {
  params: Promise<{ slug: string }>;
}

async function loadManifestNodeIds(): Promise<ReadonlySet<string>> {
  try {
    const manifestPath = path.join(
      process.cwd(),
      "public",
      "journey-manifest.json"
    );
    const raw = await fs.readFile(manifestPath, "utf8");
    const manifest = JSON.parse(raw) as JourneyManifest;
    return new Set(manifest.nodes.map((node) => node.node_id));
  } catch {
    // If the manifest is missing (local dev before Task 5 ran), the flow
    // runner still works — FlowFocusNode falls back to the API error state.
    return new Set();
  }
}

export default async function FlowRunnerPage({ params }: FlowRunnerPageProps) {
  const { slug } = await params;
  const manifestNodeIds = await loadManifestNodeIds();
  return <FlowView slug={slug} manifestNodeIds={manifestNodeIds} />;
}
