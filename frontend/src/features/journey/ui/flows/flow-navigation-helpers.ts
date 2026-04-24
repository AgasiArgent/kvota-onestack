/**
 * Pure helpers for `<FlowNavigation />`. Isolated from the component so they
 * can be unit-tested without mounting React.
 *
 * Req 18.7 — surface overall flow progress and estimated remaining time.
 */

/**
 * Estimate remaining minutes based on the step index. Assumes each step
 * takes roughly the same time (est_minutes / stepCount). The result is
 * rounded to the nearest whole minute and never goes below 0 or above
 * `estTotalMinutes`.
 *
 * At the very last step we still show the per-step estimate (not 0) so the
 * user knows "one more step ~N min" rather than being told they are done
 * before they click Next.
 */
export function formatRemainingMinutes(
  estTotalMinutes: number,
  stepIndex: number,
  stepCount: number
): number {
  if (stepCount <= 0) return 0;
  if (estTotalMinutes <= 0) return 0;
  const clampedIndex = Math.max(0, Math.min(stepIndex, stepCount - 1));
  const stepsRemaining = stepCount - clampedIndex;
  const perStep = estTotalMinutes / stepCount;
  return Math.max(0, Math.round(perStep * stepsRemaining));
}
