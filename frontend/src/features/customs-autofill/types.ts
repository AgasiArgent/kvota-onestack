/**
 * Suggestion returned by POST /api/customs/autofill.
 * Mirrors api.customs._AUTOFILL_FIELDS.
 *
 * REQ-5 customs-phase-1: extended with optional fields populated when
 * the request includes ``force_live=true`` and the resolver fallback
 * synthesises a suggestion from a live (or cached) Alta result. Existing
 * fields remain unchanged — additions are strictly optional so legacy
 * consumers are not broken.
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

  // ---- REQ-5 additive (customs-phase-1) ----------------------------------
  // Populated for both historical and force_live suggestions.
  country_of_origin_oksm?: number | null;
  has_origin_certificate?: boolean | null;
  has_fta_certificate?: boolean | null;

  // Populated only when force_live=true triggered the resolver fallback.
  customs_rates_source?: string | null;
  customs_rates_fetched_at?: string | null;
  customs_rates_summary?: string | null;
}
