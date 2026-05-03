"use client";

import { apiClient } from "@/shared/lib/api";
import type { ApiResponse } from "@/shared/lib/api";

import type {
  ClassifyData,
  ClassifyInput,
  ClassifySelectData,
  ClassifySelectRequest,
} from "../model/types";

export interface ClassifyRequest {
  items: ClassifyInput[];
}

/**
 * POST /api/customs/classify — typed wrapper.
 *
 * Burns 1 Alta Express packet per batch (idempotent on same-day retries).
 * Errors:
 *   - UNAUTHORIZED, FORBIDDEN
 *   - BAD_REQUEST       — empty items / malformed body
 *   - PACKET_EXHAUSTED  — Alta packet quota too low (cron budget protected)
 *   - ALTA_UNAVAILABLE  — Alta API errored or unreachable
 */
export async function classifyItems(
  body: ClassifyRequest,
): Promise<ApiResponse<ClassifyData>> {
  return apiClient<ClassifyData>("/customs/classify", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * POST /api/customs/classify/select — record customs-specialist's pick.
 *
 * Updates `quote_items.hs_code` AND writes an audit row to
 * `kvota.tnved_classification_log` so we can measure Express accuracy.
 */
export async function selectClassification(
  body: ClassifySelectRequest,
): Promise<ApiResponse<ClassifySelectData>> {
  return apiClient<ClassifySelectData>("/customs/classify/select", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
