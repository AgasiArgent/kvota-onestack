import { createClient } from "@/shared/lib/supabase/client";
import type { CustomsItemExpense, CustomsQuoteExpense } from "./types";

/**
 * Direct Supabase reads (no Python API needed): reading per-item/per-quote
 * expenses is a simple selection. Mutations go through the Python API —
 * see ./server-actions.ts.
 */

export async function fetchItemExpenses(
  quoteItemId: string,
): Promise<CustomsItemExpense[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("customs_item_expenses")
    .select("id, quote_item_id, label, amount_rub, notes, created_at, created_by")
    .eq("quote_item_id", quoteItemId)
    .order("created_at", { ascending: true });

  if (error) {
    console.error("fetchItemExpenses failed:", error);
    return [];
  }
  return (data ?? []) as CustomsItemExpense[];
}

export async function fetchQuoteExpenses(
  quoteId: string,
): Promise<CustomsQuoteExpense[]> {
  const supabase = createClient();
  const { data, error } = await supabase
    .from("customs_quote_expenses")
    .select("id, quote_id, label, amount_rub, notes, created_at, created_by")
    .eq("quote_id", quoteId)
    .order("created_at", { ascending: true });

  if (error) {
    console.error("fetchQuoteExpenses failed:", error);
    return [];
  }
  return (data ?? []) as CustomsQuoteExpense[];
}
