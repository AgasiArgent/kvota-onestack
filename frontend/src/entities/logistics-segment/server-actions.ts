"use server";

import { revalidatePath } from "next/cache";
import { apiServerClient } from "@/shared/lib/api-server";
import { getSessionUser } from "@/entities/user";

/**
 * logistics-segment server actions — thin wrappers over Python API.
 * Endpoints per spec §6.1.
 *
 * revalidate_path is REQUIRED (invoices have no standalone route;
 * caller passes parent quote path like "/quotes/{quote_id}").
 */

export interface SegmentPatch {
  from_location_id?: string | null;
  to_location_id?: string | null;
  label?: string | null;
  transit_days?: number | null;
  main_cost_rub?: number;
  carrier?: string | null;
  notes?: string | null;
}

export async function createSegment(input: {
  invoice_id: string;
  sequence_order: number;
  from_location_id?: string | null;
  to_location_id?: string | null;
  label?: string;
  revalidate_path: string;
}): Promise<{ segment_id: string }> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient<{ segment_id: string }>(
    "/logistics/segments",
    {
      method: "POST",
      body: JSON.stringify({
        invoice_id: input.invoice_id,
        sequence_order: input.sequence_order,
        from_location_id: input.from_location_id ?? null,
        to_location_id: input.to_location_id ?? null,
        label: input.label ?? null,
      }),
    },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось создать сегмент");
  }
  revalidatePath(input.revalidate_path);
  return res.data!;
}

export async function updateSegment(input: {
  segment_id: string;
  patch: SegmentPatch;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient(
    `/logistics/segments/${input.segment_id}`,
    {
      method: "PATCH",
      body: JSON.stringify(input.patch),
    },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось обновить сегмент");
  }
  revalidatePath(input.revalidate_path);
}

export async function deleteSegment(input: {
  segment_id: string;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient(
    `/logistics/segments/${input.segment_id}`,
    { method: "DELETE" },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось удалить сегмент");
  }
  revalidatePath(input.revalidate_path);
}

export async function reorderSegment(input: {
  segment_id: string;
  new_sequence_order: number;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient(
    `/logistics/segments/${input.segment_id}/reorder`,
    {
      method: "POST",
      body: JSON.stringify({ new_sequence_order: input.new_sequence_order }),
    },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось переставить сегмент");
  }
  revalidatePath(input.revalidate_path);
}

// --- Segment expenses -----------------------------------------------

export async function createSegmentExpense(input: {
  segment_id: string;
  label: string;
  cost_rub: number;
  days?: number;
  notes?: string;
  revalidate_path: string;
}): Promise<{ expense_id: string }> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient<{ expense_id: string }>(
    "/logistics/expenses",
    {
      method: "POST",
      body: JSON.stringify({
        segment_id: input.segment_id,
        label: input.label,
        cost_rub: input.cost_rub,
        days: input.days ?? null,
        notes: input.notes ?? null,
      }),
    },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось добавить расход");
  }
  revalidatePath(input.revalidate_path);
  return res.data!;
}

export async function deleteSegmentExpense(input: {
  expense_id: string;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient(
    `/logistics/expenses/${input.expense_id}`,
    { method: "DELETE" },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось удалить расход");
  }
  revalidatePath(input.revalidate_path);
}

// --- Completion / review --------------------------------------------

export async function completeLogistics(input: {
  invoice_id: string;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient("/logistics/complete", {
    method: "POST",
    body: JSON.stringify({ invoice_id: input.invoice_id }),
  });
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось завершить расценку");
  }
  revalidatePath(input.revalidate_path);
}

export async function acknowledgeLogisticsReview(input: {
  invoice_id: string;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient("/logistics/acknowledge-review", {
    method: "POST",
    body: JSON.stringify({ invoice_id: input.invoice_id }),
  });
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось подтвердить");
  }
  revalidatePath(input.revalidate_path);
}
