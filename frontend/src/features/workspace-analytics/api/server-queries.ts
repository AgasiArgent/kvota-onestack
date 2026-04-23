import "server-only";
import { apiServerClient } from "@/shared/lib/api-server";

/**
 * Row shape returned by GET /api/workspace/{domain}/analytics.
 * One entry per user that has completed >= 1 invoice in the domain.
 */
export interface WorkspaceAnalyticsRow {
  user_id: string;
  user_name: string;
  completed_count: number;
  median_hours: number;
  on_time_count: number;
  on_time_pct: number;
}

interface AnalyticsResponseData {
  rows: WorkspaceAnalyticsRow[];
}

/**
 * Fetch per-user completion analytics for the given workspace domain. On any
 * error (auth, network, backend) returns [] so the UI can render an empty
 * panel instead of crashing the whole page.
 */
export async function fetchWorkspaceAnalytics(
  domain: "logistics" | "customs",
): Promise<WorkspaceAnalyticsRow[]> {
  const res = await apiServerClient<AnalyticsResponseData>(
    `/workspace/${domain}/analytics`,
  );
  if (!res.success || !res.data) {
    if (res.error) {
      console.error(
        `fetchWorkspaceAnalytics(${domain}) failed:`,
        res.error.code,
        res.error.message,
      );
    }
    return [];
  }
  return res.data.rows ?? [];
}
