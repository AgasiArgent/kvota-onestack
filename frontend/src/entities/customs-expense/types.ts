/**
 * customs-expense entity — per-item + per-quote customs costs (RUB-only).
 *
 * Backed by tables (migration 293):
 *   - kvota.customs_item_expenses   (per quote_item row)
 *   - kvota.customs_quote_expenses  (per quote row)
 */

export interface CustomsItemExpense {
  id: string;
  quote_item_id: string;
  label: string;
  amount_rub: number;
  notes: string | null;
  created_at: string;
  created_by: string | null;
}

export interface CustomsQuoteExpense {
  id: string;
  quote_id: string;
  label: string;
  amount_rub: number;
  notes: string | null;
  created_at: string;
  created_by: string | null;
}
