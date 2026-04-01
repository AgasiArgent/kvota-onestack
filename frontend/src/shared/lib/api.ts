"use client";

import { createClient } from "@/shared/lib/supabase/client";

export type { ApiResponse } from "@/shared/types/api";
import type { ApiResponse } from "@/shared/types/api";

const PYTHON_API_URL = process.env.NEXT_PUBLIC_PYTHON_API_URL || "";

export async function apiClient<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const headers: Record<string, string> = {
    ...(session?.access_token
      ? { Authorization: `Bearer ${session.access_token}` }
      : {}),
  };

  // Only set Content-Type for requests with a body — GET requests with
  // Content-Type: application/json cause FastHTML to try parsing the empty body
  if (options.body) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${PYTHON_API_URL}/api${path}`, {
    ...options,
    headers: {
      ...headers,
      ...options.headers,
    },
  });

  return response.json();
}
