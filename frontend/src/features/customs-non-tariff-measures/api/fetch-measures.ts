"use client";

import { apiClient } from "@/shared/lib/api";
import type { ApiResponse } from "@/shared/lib/api";

export interface NonTariffMeasure {
  measure_type: string;
  name: string;
  description: string | null;
  document_basis: string | null;
  document_link: string | null;
  valid_from: string | null;
  valid_to: string | null;
}

export interface NonTariffMeasuresData {
  measures: NonTariffMeasure[];
  source: string;
  fetched_at: string | null;
}

export interface FetchMeasuresRequest {
  tnved_code: string;
  country_oksm: number;
  mode?: "import" | "export";
}

/**
 * POST /api/customs/non-tariff-measures — typed wrapper.
 *
 * Cost note (gotcha #5): each call is billed ~3₽ separately from the
 * Такса subscription. Trigger only on explicit user action — never on
 * page-load or automatic prefetch.
 */
export async function fetchMeasures(
  body: FetchMeasuresRequest
): Promise<ApiResponse<NonTariffMeasuresData>> {
  return apiClient<NonTariffMeasuresData>("/customs/non-tariff-measures", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
