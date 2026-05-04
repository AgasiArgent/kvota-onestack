"use client";

import { apiClient } from "@/shared/lib/api";
import type { ApiResponse } from "@/shared/lib/api";

import type { HistoryMatch } from "../model/types";

/**
 * GET /api/customs/items/history?tnved_code=&country_oksm= — typed wrapper.
 *
 * On success with a match: `{ success: true, data: HistoryMatch }`.
 * On success without history: `{ success: true, data: null }`.
 * On error: `{ success: false, error: { code, message } }`. Known codes:
 *   UNAUTHORIZED, FORBIDDEN, BAD_REQUEST.
 *
 * Used by `customs-item-dialog.tsx` to surface a previous customs choice
 * for the same `(tnved_code, country)` combination so the specialist can
 * re-apply it without re-deriving from scratch.
 */
export async function fetchHistory(
  tnvedCode: string,
  countryOksm: number,
): Promise<ApiResponse<HistoryMatch | null>> {
  return apiClient<HistoryMatch | null>(
    `/customs/items/history?tnved_code=${encodeURIComponent(tnvedCode)}&country_oksm=${countryOksm}`,
    { method: "GET" },
  );
}
