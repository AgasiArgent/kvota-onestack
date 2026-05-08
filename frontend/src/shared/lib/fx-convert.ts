/**
 * fx-convert — pure currency conversion helpers used by the
 * Route Constructor's RouteTotalsCard (РОЛ Тест 07 #3.7).
 *
 * The DB stores rates as `from_currency → to_currency` rows in
 * `kvota.exchange_rates`. To convert between any two supported currencies
 * we go via RUB:
 *
 *   amountInTarget = amount * (rateFromToRub / rateTargetToRub)
 *
 * RUB-to-RUB is identity (1.0). When a rate is missing we surface the
 * issue back to the caller (returns null) — the totals card decides
 * whether to fall back to "—" or the source-currency formatted number.
 */
export type FxRateMap = Readonly<Record<string, number>>;

/**
 * Convert `amount` from `from` currency to `to` currency using the
 * supplied rate map. The map's keys are uppercase ISO codes; each value
 * is "how many RUB per 1 unit of the foreign currency" (i.e. the
 * `from_currency = X, to_currency = RUB, rate = N` shape on
 * `kvota.exchange_rates`). RUB is implicitly 1.0 — callers must NOT
 * include it in the map.
 *
 * Returns null when a required rate is missing, so the caller can render
 * an unambiguous "rate unavailable" state instead of silently using 1.0.
 */
export function convertCurrency(
  amount: number,
  from: string,
  to: string,
  ratesToRub: FxRateMap,
): number | null {
  if (!Number.isFinite(amount)) return null;
  if (amount === 0) return 0;

  const src = from.toUpperCase();
  const dst = to.toUpperCase();
  if (src === dst) return amount;

  const srcToRub = src === "RUB" ? 1 : ratesToRub[src];
  const dstToRub = dst === "RUB" ? 1 : ratesToRub[dst];
  if (!srcToRub || !dstToRub) return null;

  return (amount * srcToRub) / dstToRub;
}

/**
 * Sum a list of `(amount, currency)` pairs into the target currency.
 * Returns `{ total, missing }`. `missing` lists the currency codes for
 * which a rate could not be resolved; their amounts are excluded from
 * `total` so the user sees a partial figure with a warning rather than a
 * misleading silent zero.
 */
export function sumInCurrency(
  entries: ReadonlyArray<{ amount: number; currency: string }>,
  target: string,
  ratesToRub: FxRateMap,
): { total: number; missing: string[] } {
  let total = 0;
  const missing = new Set<string>();
  for (const e of entries) {
    const converted = convertCurrency(e.amount, e.currency, target, ratesToRub);
    if (converted == null) {
      missing.add(e.currency.toUpperCase());
    } else {
      total += converted;
    }
  }
  return { total, missing: Array.from(missing).sort() };
}
