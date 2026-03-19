import { createClient } from "@/shared/lib/supabase/client";

interface SaveCurrencyInvoiceInput {
  seller_entity_type: string | null;
  seller_entity_id: string | null;
  buyer_entity_type: string | null;
  buyer_entity_id: string | null;
  markup_percent: number;
}

export async function saveCurrencyInvoice(
  id: string,
  orgId: string,
  input: SaveCurrencyInvoiceInput
): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("currency_invoices")
    .update({
      seller_entity_type: input.seller_entity_type,
      seller_entity_id: input.seller_entity_id,
      buyer_entity_type: input.buyer_entity_type,
      buyer_entity_id: input.buyer_entity_id,
      markup_percent: input.markup_percent,
      updated_at: new Date().toISOString(),
    })
    .eq("id", id)
    .eq("organization_id", orgId);

  if (error) throw error;
}

export async function verifyCurrencyInvoice(
  id: string,
  orgId: string
): Promise<void> {
  const supabase = createClient();

  const { error } = await supabase
    .from("currency_invoices")
    .update({
      status: "verified",
      verified_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("id", id)
    .eq("organization_id", orgId);

  if (error) throw error;
}
