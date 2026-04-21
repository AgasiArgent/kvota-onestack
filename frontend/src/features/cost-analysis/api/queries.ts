import { apiServerClient } from "@/shared/lib/api-server";
import type { ApiResponse } from "@/shared/types/api";
import type { CostAnalysisView } from "../types";

/**
 * Fetch cost-analysis data for a quote via the FastAPI endpoint.
 * Server-only: uses the session JWT to authenticate to Python.
 */
export async function fetchCostAnalysis(
  quoteId: string
): Promise<ApiResponse<CostAnalysisView>> {
  return apiServerClient<CostAnalysisView>(
    `/quotes/${encodeURIComponent(quoteId)}/cost-analysis`
  );
}
