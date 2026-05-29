/**
 * historical-fx — pure helpers for converting per-КПП purchase totals into
 * USD using the FX rate effective on the КПП's creation date.
 *
 * Used by the /suppliers aggregate "Сумма КПП" column (Testing 2 row 84
 * follow-up). The product decision: each invoice's `purchase_price_original
 * * quantity` line is converted to USD using the historical FX rate looked
 * up by the invoice's `created_at` date, then summed across the supplier.
 * The displayed value is rounded to integer USD.
 *
 * `kvota.exchange_rates` rows are `from_currency → to_currency = RUB`,
 * fetched_at = timestamp the rate was captured. RUB has no row of its own
 * — it's the implicit base (1.0). So to convert FOO → USD on date D:
 *
 *   foo_to_rub = rate(FOO, "RUB", on D)
 *   usd_to_rub = rate("USD", "RUB", on D)
 *   amount_usd = amount_foo * foo_to_rub / usd_to_rub
 *
 * USD → USD is identity. We never error on missing rates — the КПП is
 * skipped and surfaced via the `missing` warning channel so the caller
 * can log it without breaking the table render.
 */

/**
 * One row from kvota.exchange_rates restricted to the columns we use.
 * `fetched_at` is ISO 8601 UTC.
 */
export interface FxRateRow {
  from_currency: string;
  rate: number;
  fetched_at: string;
}

/**
 * Currency code → list of (timestamp, rate) tuples, sorted DESC by timestamp.
 * `pickRateOnOrBefore` walks the list once per lookup; for the typical
 * dataset (≤ a few hundred rate rows) this is more than fast enough and
 * avoids pulling in a sorted-tree dependency.
 */
export type HistoricalRateMap = ReadonlyMap<
  string,
  ReadonlyArray<{ fetched_at: string; rate: number }>
>;

/**
 * Group raw exchange_rates rows by currency, sorted newest-first.
 * Caller should already have filtered to `to_currency = 'RUB'`.
 */
export function buildHistoricalRateMap(
  rows: ReadonlyArray<FxRateRow>,
): HistoricalRateMap {
  const acc = new Map<string, Array<{ fetched_at: string; rate: number }>>();
  for (const row of rows) {
    const currency = row.from_currency.toUpperCase();
    if (!Number.isFinite(row.rate) || row.rate <= 0) continue;
    const bucket = acc.get(currency) ?? [];
    bucket.push({ fetched_at: row.fetched_at, rate: row.rate });
    acc.set(currency, bucket);
  }
  // Sort each bucket DESC (newest first). Stable lookups regardless of
  // input order.
  for (const bucket of acc.values()) {
    bucket.sort((a, b) => (a.fetched_at < b.fetched_at ? 1 : -1));
  }
  return acc;
}

/**
 * Find the rate for `currency` effective at `asOf`. Returns the most
 * recent rate whose `fetched_at <= asOf`; if no rate is recorded before
 * that date, falls back to the earliest available rate (so a КПП created
 * before we started archiving FX still gets a sensible figure rather than
 * being silently dropped). Returns null if the currency has no rates at all.
 */
export function pickRateOnOrBefore(
  rates: HistoricalRateMap,
  currency: string,
  asOf: string,
): number | null {
  const key = currency.toUpperCase();
  if (key === "RUB") return 1;
  const bucket = rates.get(key);
  if (!bucket || bucket.length === 0) return null;
  // Bucket is sorted DESC — the first entry with fetched_at <= asOf wins.
  for (const entry of bucket) {
    if (entry.fetched_at <= asOf) return entry.rate;
  }
  // No rate on or before asOf — fall back to earliest known rate (oldest
  // entry, which is at the end of a DESC-sorted list).
  return bucket[bucket.length - 1].rate;
}

/**
 * Convert `amount` from `from` to `to` on the date `asOf` using the
 * historical rate map. Both legs are resolved against `* → RUB` rates
 * (RUB is the implicit base, rate = 1):
 *
 *   from_to_rub = rate(from, "RUB", on asOf)
 *   to_to_rub   = rate(to,   "RUB", on asOf)
 *   amount_to   = amount * from_to_rub / to_to_rub
 *
 * Identity when `from === to`. Returns 0 for zero amounts regardless of
 * rate availability — callers don't need to special-case zero. Returns
 * null when either leg's rate is missing entirely (the currency has no
 * rows in the map) or the destination rate is zero.
 */
export function convertOnDate(
  amount: number,
  from: string,
  to: string,
  asOf: string,
  rates: HistoricalRateMap,
): number | null {
  if (!Number.isFinite(amount)) return null;
  if (amount === 0) return 0;
  const src = from.toUpperCase();
  const dst = to.toUpperCase();
  if (src === dst) return amount;

  const srcToRub = pickRateOnOrBefore(rates, src, asOf);
  if (srcToRub == null) return null;

  // RUB is the base — its rate is 1. pickRateOnOrBefore already returns 1
  // for RUB, but we keep it explicit so a missing-USD-row case still
  // resolves the RUB leg correctly.
  const dstToRub = dst === "RUB" ? 1 : pickRateOnOrBefore(rates, dst, asOf);
  if (dstToRub == null || dstToRub === 0) return null;

  return (amount * srcToRub) / dstToRub;
}

/**
 * Convert `amount` from `currency` to USD on the date `asOf` using the
 * historical rate map. Thin wrapper over {@link convertOnDate} with the
 * destination fixed to USD — kept for the /suppliers caller and existing
 * historical-fx tests. Returns null when either the source rate or the
 * USD rate is missing entirely; returns 0 for zero amounts.
 */
export function convertToUsdOnDate(
  amount: number,
  currency: string,
  asOf: string,
  rates: HistoricalRateMap,
): number | null {
  return convertOnDate(amount, currency, "USD", asOf, rates);
}

/**
 * Per-invoice line used by the /suppliers aggregate.
 * `amount = quantity * purchase_price_original` in `currency` on `asOf`.
 */
export interface InvoiceLineForUsd {
  amount: number;
  currency: string;
  asOf: string;
}

/**
 * Sum a list of invoice lines, each converted to USD using the historical
 * rate on its own `asOf` date. Returns `{ totalUsd, missing }`. Lines whose
 * rate cannot be resolved are excluded from `totalUsd` and reported in
 * `missing` (deduplicated by currency code) so the caller can log a
 * warning instead of silently rendering a smaller-than-real number.
 */
export function sumInvoiceLinesInUsd(
  lines: ReadonlyArray<InvoiceLineForUsd>,
  rates: HistoricalRateMap,
): { totalUsd: number; missing: string[] } {
  let totalUsd = 0;
  const missing = new Set<string>();
  for (const line of lines) {
    const converted = convertToUsdOnDate(
      line.amount,
      line.currency,
      line.asOf,
      rates,
    );
    if (converted == null) {
      missing.add(line.currency.toUpperCase());
    } else {
      totalUsd += converted;
    }
  }
  return { totalUsd, missing: Array.from(missing).sort() };
}
