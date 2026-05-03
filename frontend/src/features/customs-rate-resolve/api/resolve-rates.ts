"use client";

import { apiClient } from "@/shared/lib/api";
import type { ApiResponse } from "@/shared/lib/api";

import type { ResolveRatesData } from "../model/types";

export interface ResolveRatesRequest {
  tnved_code: string;
  country_oksm: number;
  date?: string; // ISO YYYY-MM-DD; backend defaults to today
  certificate?: boolean;
  sp_certificate?: boolean;
  quote_item_id?: string;
  has_fta_certificate?: boolean;
  /**
   * Bypass the resolver's 30-day cache TTL. Phase 1: backend currently
   * accepts the flag but the resolver always honors its own TTL — sending
   * `true` is reserved for forward-compat with Task 8 freeze.
   */
  force_live?: boolean;
  /**
   * Restrict resolution to specific payment types. Defaults to the backend's
   * `(IMP, NDS, AKC, IMPCOMP, IMPDEMP, IMPTMP, IMPDOP)` set.
   */
  include_payment_types?: string[];
}

/**
 * POST /api/customs/resolve-rates — typed wrapper.
 *
 * On success: `{ success: true, data: ResolveRatesData }`.
 * On error: `{ success: false, error: { code, message } }`. Known codes:
 *   UNAUTHORIZED, FORBIDDEN, BAD_REQUEST, INVALID_TNVED_CODE, INVALID_OKSM,
 *   ALTA_UNAVAILABLE, FREEZE_ABORTED (Task 8 forward-compat).
 */
export async function resolveRates(
  body: ResolveRatesRequest
): Promise<ApiResponse<ResolveRatesData>> {
  return apiClient<ResolveRatesData>("/customs/resolve-rates", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
