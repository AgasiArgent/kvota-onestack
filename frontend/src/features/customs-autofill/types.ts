/**
 * Suggestion returned by POST /api/customs/autofill.
 * Mirrors api.customs._AUTOFILL_FIELDS.
 */
export interface CustomsAutofillSuggestion {
  item_id: string;
  source_quote_id: string;
  source_quote_idn: string;
  source_created_at: string | null;

  hs_code: string | null;
  customs_duty: number | null;
  customs_duty_per_kg: number | null;
  customs_util_fee: number | null;
  customs_excise: number | null;
  customs_eco_fee: number | null;
  customs_honest_mark: string | null;

  license_ds_required: boolean | null;
  license_ss_required: boolean | null;
  license_sgr_required: boolean | null;

  license_ds_cost: number | null;
  license_ss_cost: number | null;
  license_sgr_cost: number | null;
}
