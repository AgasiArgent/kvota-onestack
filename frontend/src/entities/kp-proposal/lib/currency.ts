/**
 * Currency lookup table — mirrors `CURRENCIES` in `services/kp_export.py`.
 *
 * Single source of truth on the frontend for the symbol shown after each
 * monetary value and the human-readable name displayed in the form
 * selector. Whenever the Python table grows (new code), this must grow
 * with it — there is no runtime fetch.
 *
 * AED falls back to the ISO code as its visible symbol because Inter has
 * no Arabic shaping; the Python renderer follows the same rule, so the
 * preview never disagrees with the rendered PDF.
 */

import type { CurrencyCode } from "../model/types";

export interface CurrencyEntry {
  readonly code: CurrencyCode;
  readonly symbol: string;
  readonly name: string;
}

export const CURRENCIES: readonly CurrencyEntry[] = [
  { code: "RUB", symbol: "₽", name: "Российский рубль" },
  { code: "USD", symbol: "$", name: "Доллар США" },
  { code: "EUR", symbol: "€", name: "Евро" },
  { code: "CNY", symbol: "¥", name: "Китайский юань" },
  { code: "AED", symbol: "AED", name: "Дирхам ОАЭ" },
  { code: "TRY", symbol: "₺", name: "Турецкая лира" },
];

const FALLBACK: CurrencyEntry = CURRENCIES[0]!;

export function currencyEntry(code: string): CurrencyEntry {
  return CURRENCIES.find((c) => c.code === code) ?? FALLBACK;
}

export function currencySymbol(code: string): string {
  return currencyEntry(code).symbol;
}

/**
 * Format used at the first prominent monetary reference (the
 * "Сумма КП:" headline). Returns "₽ (RUB)" / "$ (USD)" — but collapses
 * to a single token (e.g. "AED") when symbol equals code, since
 * "AED (AED)" is visual noise.
 */
export function headlineSuffix(code: string): string {
  const entry = currencyEntry(code);
  return entry.symbol === entry.code
    ? entry.symbol
    : `${entry.symbol} (${entry.code})`;
}
