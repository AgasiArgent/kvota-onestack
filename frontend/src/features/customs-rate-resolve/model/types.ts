/**
 * Types for the customs-rate-resolve feature.
 *
 * Mirrors the JSON envelope of `POST /api/customs/resolve-rates` in
 * `api/customs.py:_serialize_rate` and the `resolve_rates_handler` response.
 *
 * Phase 1 caveat (per Task 5 report): `calculated_amount_rub` is always null
 * and `total_rub` is null because the request body does not carry
 * `customs_value_rub`/`weight_kg`/`quantity`/`currency_rates`. UI surfaces
 * rates as "inspection only" — show the raw rate string + payment_type label.
 */

export interface ResolvedRate {
  payment_type: string;
  value_1_number: number | null;
  value_1_unit: string | null;
  value_1_currency: string | null;
  value_2_number: number | null;
  value_2_unit: string | null;
  value_2_currency: string | null;
  sign_1: string | null;
  raw_value_string: string | null;
  /** Phase 1: always null — backend lacks customs_value/weight/quantity inputs. */
  calculated_amount_rub: number | null;
}

export interface ResolveRatesData {
  rates: ResolvedRate[];
  /** Phase 1: always null. Forward-compat with future computed-total endpoint. */
  total_rub: number | null;
  /** "alta-live" | "alta-revalidate" | "cache" | "unknown" */
  source: string;
  /** ISO-8601 timestamp of the most recent rate fetch. */
  fetched_at: string | null;
  /**
   * Forward-compat with Task 8 (freeze): non-blocking warnings (Tier 2).
   * Currently never populated in Phase 1 resolve-rates response.
   */
  warnings?: string[];
}

export interface ApiError {
  code: string;
  message: string;
}

/** Russian labels for known payment_type codes (subset used in UI). */
export const PAYMENT_TYPE_LABELS: Record<string, string> = {
  IMP: "Пошлина",
  NDS: "НДС",
  AKC: "Акциз",
  IMPCOMP: "Антидемпинговая",
  IMPDEMP: "Антидемпинговая (доп.)",
  IMPTMP: "Сезонная",
  IMPDOP: "Доп. пошлина",
  EXP: "Экспортная пошлина",
};

export function paymentTypeLabel(code: string): string {
  return PAYMENT_TYPE_LABELS[code] ?? code;
}
