"use server";

import { revalidatePath } from "next/cache";
import { apiServerClient } from "@/shared/lib/api-server";
import { getSessionUser } from "@/entities/user";

/**
 * customs-expense server actions — thin wrappers over Python API.
 * Endpoints per logistics-customs-redesign design §6.2.
 *
 * revalidate_path is always the parent quote path (e.g. "/quotes/{id}") —
 * expenses have no standalone route.
 */

// ---------- Per-item -------------------------------------------------

export async function createItemExpense(input: {
  quote_item_id: string;
  label: string;
  amount_rub: number;
  notes?: string | null;
  revalidate_path: string;
}): Promise<{ expense_id: string }> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient<{ expense_id: string }>(
    `/customs/items/${input.quote_item_id}/expenses`,
    {
      method: "POST",
      body: JSON.stringify({
        label: input.label,
        amount_rub: input.amount_rub,
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

export async function deleteItemExpense(input: {
  expense_id: string;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient(
    `/customs/items/expenses/${input.expense_id}`,
    { method: "DELETE" },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось удалить расход");
  }
  revalidatePath(input.revalidate_path);
}

// ---------- Per-quote ------------------------------------------------

export async function createQuoteExpense(input: {
  quote_id: string;
  label: string;
  amount_rub: number;
  notes?: string | null;
  revalidate_path: string;
}): Promise<{ expense_id: string }> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient<{ expense_id: string }>(
    `/customs/quotes/${input.quote_id}/expenses`,
    {
      method: "POST",
      body: JSON.stringify({
        label: input.label,
        amount_rub: input.amount_rub,
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

export async function deleteQuoteExpense(input: {
  expense_id: string;
  revalidate_path: string;
}): Promise<void> {
  const user = await getSessionUser();
  if (!user) throw new Error("Unauthorized");

  const res = await apiServerClient(
    `/customs/quotes/expenses/${input.expense_id}`,
    { method: "DELETE" },
  );
  if (!res.success) {
    throw new Error(res.error?.message ?? "Не удалось удалить расход");
  }
  revalidatePath(input.revalidate_path);
}
