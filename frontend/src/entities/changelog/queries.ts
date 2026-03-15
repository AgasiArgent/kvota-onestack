import { apiServerClient } from "@/shared/lib/api-server";
import type { ChangelogEntry } from "./types";

export async function fetchChangelogEntries(): Promise<ChangelogEntry[]> {
  try {
    const res = await apiServerClient<ChangelogEntry[]>("/changelog");

    console.log("[changelog] API response:", JSON.stringify(res).substring(0, 200));

    if (!res.success || !res.data) {
      console.log("[changelog] Returning empty - success:", res.success, "data:", !!res.data);
      return [];
    }

    return res.data;
  } catch (err) {
    console.error("[changelog] Fetch error:", err);
    return [];
  }
}
