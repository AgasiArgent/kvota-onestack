import { createAdminClient } from "@/shared/lib/supabase/server";
import type {
  CustomsDeclaration,
  CustomsDeclarationItem,
} from "./types";

export async function fetchDeclarations(
  orgId: string
): Promise<CustomsDeclaration[]> {
  const admin = createAdminClient();

  // Fetch declarations
  const { data: declarations, error } = await admin
    .from("customs_declarations")
    .select("id, regnum, declaration_date, sender_name, internal_ref, total_customs_value_rub, total_duty_rub, total_fee_rub")
    .eq("organization_id", orgId)
    .order("declaration_date", { ascending: false });

  if (error) throw error;
  if (!declarations || declarations.length === 0) return [];

  // Batch-fetch item counts and match counts
  const declIds = declarations.map((d) => d.id);
  const { data: items } = await admin
    .from("customs_declaration_items")
    .select("id, declaration_id, deal_id")
    .in("declaration_id", declIds);

  // Build count maps
  const itemCountMap = new Map<string, number>();
  const matchCountMap = new Map<string, number>();
  for (const item of items ?? []) {
    itemCountMap.set(item.declaration_id, (itemCountMap.get(item.declaration_id) ?? 0) + 1);
    if (item.deal_id) {
      matchCountMap.set(item.declaration_id, (matchCountMap.get(item.declaration_id) ?? 0) + 1);
    }
  }

  return declarations.map((d) => ({
    id: d.id,
    regnum: d.regnum,
    declaration_date: d.declaration_date,
    sender_name: d.sender_name,
    internal_ref: d.internal_ref,
    total_customs_value_rub: d.total_customs_value_rub,
    total_duty_rub: d.total_duty_rub,
    total_fee_rub: d.total_fee_rub,
    item_count: itemCountMap.get(d.id) ?? 0,
    matched_count: matchCountMap.get(d.id) ?? 0,
  }));
}

export async function fetchDeclarationItems(
  declarationId: string,
  orgId: string
): Promise<CustomsDeclarationItem[]> {
  const admin = createAdminClient();

  // Verify declaration belongs to org
  const { data: decl } = await admin
    .from("customs_declarations")
    .select("id")
    .eq("id", declarationId)
    .eq("organization_id", orgId)
    .single();

  if (!decl) return [];

  const { data, error } = await admin
    .from("customs_declaration_items")
    .select("id, declaration_id, block_number, item_number, sku, description, manufacturer, brand, quantity, unit, gross_weight_kg, net_weight_kg, invoice_cost, invoice_currency, hs_code, customs_value_rub, fee_amount_rub, duty_amount_rub, vat_amount_rub, deal_id, matched_at")
    .eq("declaration_id", declarationId)
    .order("item_number", { ascending: true });

  if (error) throw error;

  return (data ?? []).map((item) => ({
    id: item.id,
    declaration_id: item.declaration_id,
    block_number: item.block_number,
    item_number: item.item_number,
    sku: item.sku,
    description: item.description,
    manufacturer: item.manufacturer,
    brand: item.brand,
    quantity: item.quantity,
    unit: item.unit,
    gross_weight_kg: item.gross_weight_kg,
    net_weight_kg: item.net_weight_kg,
    invoice_cost: item.invoice_cost,
    invoice_currency: item.invoice_currency,
    hs_code: item.hs_code,
    customs_value_rub: item.customs_value_rub,
    fee_amount_rub: item.fee_amount_rub,
    duty_amount_rub: item.duty_amount_rub,
    vat_amount_rub: item.vat_amount_rub,
    deal_id: item.deal_id,
    matched_at: item.matched_at,
  }));
}
