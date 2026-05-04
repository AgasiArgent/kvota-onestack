/**
 * Pure proportional cost-split helper for shared customs certificates.
 *
 * Phase B (customs-shared-certificates) — REQ-3.
 *
 * Distributes a certificate's cost (`certCost`, RUB) across attached
 * quote-positions in proportion to each position's RUB cost basis.
 * The RUB cost basis must be supplied by the caller already in RUB
 * (frontend computes it via `purchase_price_original × quantity ×
 * currency_rate_to_rub` — see REQ-3 AC#4).
 *
 * Sister Python implementation lives in `services/cost_split.py`. Both
 * modules consume the same JSON fixtures (`tests/fixtures/cost_split_fixtures.json`)
 * and must produce kopek-identical output.
 *
 * Implementation note: this module uses an explicit half-up rounding
 * shim — `Math.floor(value * 100 + 0.5) / 100` — instead of `Math.round`
 * to stay parity-compatible with Python's `Decimal.quantize('0.01',
 * ROUND_HALF_UP)`. `Math.round`'s historical/engine-dependent behaviour
 * around the .5 boundary is unsafe for cross-language parity (LD-6).
 *
 * No external dependencies — pure arithmetic.
 */

/**
 * Half-up shim — equivalent of `Decimal.quantize('0.01', ROUND_HALF_UP)`.
 *
 * NOT `Math.round` — banker's rounding on .5 is not guaranteed by the spec
 * and would drift vs Python's ROUND_HALF_UP.
 *
 * Inputs are non-negative in production (CHECK `cost_rub >= 0` on DB,
 * validation on API). The shim is documented to operate on non-negative
 * inputs only; behaviour for negatives matches `Math.floor`-toward-minus-
 * infinity semantics, which is acceptable for the asserted invariants.
 */
export function roundHalfUp2(value: number): number {
  return Math.floor(value * 100 + 0.5) / 100;
}

/**
 * Proportional share for a single item, rounded to kopeks.
 *
 * Mirrors `services.cost_split.split_cost`:
 *  - `totalItemsValue === 0` → returns `0` (the equal-split fallback is a
 *    batch-level concern; single-share callers must use `splitCostBatch`).
 *  - `certCost === 0` → returns `0`.
 *  - Otherwise: `roundHalfUp2((itemValue / totalItemsValue) * certCost)`.
 */
export function splitCost(
  itemValue: number,
  totalItemsValue: number,
  certCost: number,
): number {
  if (totalItemsValue === 0) {
    return 0;
  }
  if (certCost === 0) {
    return 0;
  }
  const share = (itemValue / totalItemsValue) * certCost;
  return roundHalfUp2(share);
}

/**
 * Compute kopek-exact shares for all items.
 *
 * Mirrors `services.cost_split.split_cost_batch`:
 *  - `itemValues[]` ordered (typically by `created_at` ASC).
 *  - empty array            → `[]`
 *  - single item            → `[certCost]` (no rounding — full cost)
 *  - all-zero basis (sum === 0) → equal split `certCost / N`; last item
 *                                 absorbs the rounding residual.
 *  - normal proportional    → first `N-1` shares via `splitCost`; last
 *                             share = `certCost - sum(others)` so that
 *                             `sum(result) === certCost` exactly
 *                             (REQ-3 AC#7 — residual rule).
 *
 * The last share is also passed through `roundHalfUp2` to clean up
 * floating-point drift introduced by the subtraction. The shares are
 * already kopek-aligned, so the residual itself is < 1e-10 in practice
 * and rounds back to its intended kopek value.
 */
export function splitCostBatch(
  itemValues: readonly number[],
  certCost: number,
): number[] {
  const n = itemValues.length;
  if (n === 0) {
    return [];
  }
  if (n === 1) {
    return [certCost];
  }

  let total = 0;
  for (const v of itemValues) {
    total += v;
  }

  if (total === 0) {
    // Equal-split fallback — divide certCost by N, last absorbs residual.
    const equal = roundHalfUp2(certCost / n);
    const shares: number[] = [];
    for (let i = 0; i < n - 1; i += 1) {
      shares.push(equal);
    }
    let sumOthers = 0;
    for (const s of shares) {
      sumOthers += s;
    }
    shares.push(roundHalfUp2(certCost - sumOthers));
    return shares;
  }

  // Normal proportional path.
  const shares: number[] = [];
  for (let i = 0; i < n - 1; i += 1) {
    shares.push(splitCost(itemValues[i], total, certCost));
  }
  let sumOthers = 0;
  for (const s of shares) {
    sumOthers += s;
  }
  shares.push(roundHalfUp2(certCost - sumOthers));
  return shares;
}
