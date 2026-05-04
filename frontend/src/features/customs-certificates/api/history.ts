"use client";

/**
 * Typed wrapper for the certificate history endpoint (Phase B Task 5 / REQ-5).
 *
 * Endpoint: `GET /api/customs/certificates/history`
 *   Query: hs_code? & brand? & supplier_id? & current_quote_id (required)
 *   200:   { success: true, data: { match: HistoryCertMatch | null } }
 *
 * The server runs a loose 2-of-3 match (hs_code, brand, supplier_id) over
 * the past 12 months in the same organization, excluding the current quote
 * (see `services/quote_certificates_history.py`). When the predicate
 * cannot be satisfied — or the DB throws — the server returns
 * `data.match = null` (history is best-effort, never raises 5xx).
 *
 * The frontend uses the result to render `HistoryBanner` (REQ-5 AC#4) —
 * variant chosen from `match.is_actual` per REQ-4 AC#5/#6.
 */
import { apiClient } from "@/shared/lib/api";

import type { ApiResponse, CertificateHistoryData } from "../model/types";

export interface FetchCertificateHistoryArgs {
  /** Optional — null/empty contributes 0 to the 2-of-3 counter. */
  hsCode?: string;
  /** Optional — null/empty contributes 0 to the 2-of-3 counter. */
  brand?: string;
  /** Optional — null/empty contributes 0 to the 2-of-3 counter. */
  supplierId?: string;
  /**
   * UUID of the quote being edited — server excludes this quote from
   * candidates so editing a quote doesn't match its own certs back to
   * itself (REQ-5 AC#1 last bullet).
   */
  currentQuoteId: string;
}

/**
 * Fetch a recent matching certificate (or `null`) for the given filters.
 *
 * Build behaviour: empty/undefined query params are omitted from the URL
 * — the server tolerates either omission or `?param=` (empty string),
 * but skipping them keeps logs clean.
 */
export function fetchCertificateHistory(
  args: FetchCertificateHistoryArgs,
): Promise<ApiResponse<CertificateHistoryData>> {
  const params = new URLSearchParams();
  params.set("current_quote_id", args.currentQuoteId);
  if (args.hsCode) params.set("hs_code", args.hsCode);
  if (args.brand) params.set("brand", args.brand);
  if (args.supplierId) params.set("supplier_id", args.supplierId);

  return apiClient<CertificateHistoryData>(
    `/customs/certificates/history?${params.toString()}`,
    { method: "GET" },
  );
}
