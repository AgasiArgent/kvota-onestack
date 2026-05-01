import { createClient } from "@/shared/lib/supabase/server";

export type { ApiResponse } from "@/shared/types/api";
import type { ApiResponse } from "@/shared/types/api";

const PYTHON_API_URL = process.env.PYTHON_API_URL || "http://localhost:5001";

export async function apiServerClient<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const method = (options.method ?? "GET").toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD" && method !== "DELETE";

  const response = await fetch(`${PYTHON_API_URL}/api${path}`, {
    ...options,
    // SSR-side calls to the Python API must be uncached — pages like the
    // procurement kanban depend on per-request session context AND on
    // mutations that aren't routed through Next.js cache invalidation
    // (e.g. backfill SQL, Python-side workflow transitions). Default
    // fetch caching could surface stale rows after a backend mutation.
    cache: "no-store",
    headers: {
      ...(hasBody ? { "Content-Type": "application/json" } : {}),
      ...(session?.access_token
        ? { Authorization: `Bearer ${session.access_token}` }
        : {}),
      ...options.headers,
    },
  });

  const text = await response.text();
  try {
    return JSON.parse(text) as ApiResponse<T>;
  } catch {
    return {
      success: false,
      error: { code: "PARSE_ERROR", message: `HTTP ${response.status}` },
    };
  }
}
