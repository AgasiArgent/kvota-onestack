import type { ChangelogEntry } from "./types";

const PYTHON_API_URL = process.env.PYTHON_API_URL || "http://localhost:5001";

export async function fetchChangelogEntries(): Promise<ChangelogEntry[]> {
  try {
    const response = await fetch(`${PYTHON_API_URL}/api/changelog`, {
      cache: "no-store",
    });
    if (!response.ok) return [];
    const json = await response.json();
    return json.success ? json.data : [];
  } catch {
    return [];
  }
}
