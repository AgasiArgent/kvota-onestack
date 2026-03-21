export interface CustomsDeclarationItem {
  id: string;
  declaration_id: string;
  block_number: number | null;
  item_number: number | null;
  sku: string | null;
  description: string | null;
  manufacturer: string | null;
  brand: string | null;
  quantity: number | null;
  unit: string | null;
  gross_weight_kg: number | null;
  net_weight_kg: number | null;
  invoice_cost: number | null;
  invoice_currency: string | null;
  hs_code: string | null;
  customs_value_rub: number | null;
  fee_amount_rub: number | null;
  duty_amount_rub: number | null;
  vat_amount_rub: number | null;
  deal_id: string | null;
  matched_at: string | null;
}

export interface CustomsDeclaration {
  id: string;
  regnum: string;
  declaration_date: string | null;
  sender_name: string | null;
  internal_ref: string | null;
  total_customs_value_rub: number | null;
  total_duty_rub: number | null;
  total_fee_rub: number | null;
  item_count: number;
  matched_count: number;
}

export interface CustomsDeclarationWithItems extends CustomsDeclaration {
  items: CustomsDeclarationItem[];
}
