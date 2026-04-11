/**
 * Shared frontend currency module — mirrors `services/currency_service.SUPPORTED_CURRENCIES`
 * (the backend source of truth). Order must match. When adding a new currency, update BOTH
 * this file and the Python module in the same commit.
 */

export const SUPPORTED_CURRENCIES = [
  "USD",
  "EUR",
  "RUB",
  "CNY",
  "TRY",
  "AED",
  "KZT",
  "JPY",
  "GBP",
  "CHF",
] as const;

export type SupportedCurrency = (typeof SUPPORTED_CURRENCIES)[number];

export const CURRENCY_LABELS: Readonly<Record<SupportedCurrency, string>> = {
  USD: "USD ($)",
  EUR: "EUR (€)",
  RUB: "RUB (₽)",
  CNY: "CNY (¥)",
  TRY: "TRY (₺)",
  AED: "AED (د.إ)",
  KZT: "KZT (₸)",
  JPY: "JPY (¥)",
  GBP: "GBP (£)",
  CHF: "CHF (₣)",
};

/**
 * Type guard: returns true when `code` matches one of the 10 supported
 * currency codes, case-insensitive. Returns false for null/undefined/empty.
 */
export function isSupportedCurrency(
  code: string | null | undefined,
): code is SupportedCurrency {
  if (!code) return false;
  return (SUPPORTED_CURRENCIES as readonly string[]).includes(
    code.toUpperCase(),
  );
}
