import { apiServerClient } from "@/shared/lib/api-server";
import type { ChangelogEntry } from "./types";

export async function fetchChangelogEntries(): Promise<ChangelogEntry[]> {
  const res = await apiServerClient<ChangelogEntry[]>("/changelog");

  if (!res.success || !res.data) {
    return [];
  }

  return res.data;
}
