import { apiClient } from "@/shared/lib/api";
import type {
  PlanFactItem,
  PlanFactCategory,
  CreatePlanFactPayload,
  RecordActualPayload,
  QuoteSearchResult,
} from "@/entities/finance";

export class PlanFactApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "PlanFactApiError";
  }
}

export async function fetchPlanFactItems(
  dealId: string,
): Promise<PlanFactItem[]> {
  const result = await apiClient<PlanFactItem[]>(
    `/plan-fact/${dealId}/items`,
  );

  if (!result.success) {
    throw new PlanFactApiError(
      result.error?.code ?? "UNKNOWN",
      result.error?.message ?? "Failed to fetch plan-fact items",
    );
  }

  return result.data ?? [];
}

export async function createPlanFactItem(
  dealId: string,
  payload: CreatePlanFactPayload,
): Promise<PlanFactItem> {
  const result = await apiClient<PlanFactItem>(
    `/plan-fact/${dealId}/items`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

  if (!result.success) {
    throw new PlanFactApiError(
      result.error?.code ?? "UNKNOWN",
      result.error?.message ?? "Failed to create plan-fact item",
    );
  }

  return result.data!;
}

export async function recordActualPayment(
  dealId: string,
  itemId: string,
  payload: RecordActualPayload,
): Promise<PlanFactItem> {
  const result = await apiClient<PlanFactItem>(
    `/plan-fact/${dealId}/items/${itemId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );

  if (!result.success) {
    throw new PlanFactApiError(
      result.error?.code ?? "UNKNOWN",
      result.error?.message ?? "Failed to record actual payment",
    );
  }

  return result.data!;
}

export async function deletePlanFactItem(
  dealId: string,
  itemId: string,
): Promise<void> {
  const result = await apiClient(`/plan-fact/${dealId}/items/${itemId}`, {
    method: "DELETE",
  });

  if (!result.success) {
    throw new PlanFactApiError(
      result.error?.code ?? "UNKNOWN",
      result.error?.message ?? "Failed to delete plan-fact item",
    );
  }
}

export async function fetchPlanFactCategories(): Promise<PlanFactCategory[]> {
  const result = await apiClient<PlanFactCategory[]>(
    `/plan-fact/categories`,
  );

  if (!result.success) {
    throw new PlanFactApiError(
      result.error?.code ?? "UNKNOWN",
      result.error?.message ?? "Failed to fetch categories",
    );
  }

  return result.data ?? [];
}

export async function searchQuotes(
  query: string,
): Promise<QuoteSearchResult[]> {
  const result = await apiClient<QuoteSearchResult[]>(
    `/quotes/search?q=${encodeURIComponent(query)}`,
  );

  if (!result.success) {
    throw new PlanFactApiError(
      result.error?.code ?? "UNKNOWN",
      result.error?.message ?? "Failed to search quotes",
    );
  }

  return result.data ?? [];
}
