/**
 * RUB cost formatter for the customs-certificates UI (Phase B, Wave 3 Task 6).
 *
 * Pure function — no DOM dependencies. Tested in `format-rub.test.ts`.
 *
 * Output convention (matches the figma mockup
 * `docs/mockups/customs-after-phases.html`):
 *
 *   formatRub(12500)        → "12 500 ₽"
 *   formatRub(999999.99)    → "999 999,99 ₽"
 *   formatRub(0)            → "0 ₽"
 *   formatRub(150)          → "150 ₽"
 *
 * Locale: `ru-RU` — uses NBSP (U+00A0) as the thousand separator and a
 * comma as the decimal separator. `Number.toLocaleString('ru-RU')` on
 * Node and modern browsers both produce NBSP, so the output is consistent
 * between SSR and CSR.
 *
 * Decimal handling: kopeks are rendered only when the input has a
 * fractional component — integer values keep a clean "150 ₽" instead of
 * "150,00 ₽" to match the mockup typography (whole-RUB summaries dominate
 * the cert UI; kopek precision shows up on shares).
 *
 * Project audit (per design.md §4.8): a project-wide `formatRub` helper
 * does not exist in `@/shared/lib/`. There is a feature-local
 * `customs-rate-resolve/lib/duty-formula.ts:formatRub` but it omits the
 * "₽" suffix and is scoped to the duty-formula preview. If a third use
 * case appears we'll lift this implementation into `@/shared/lib/`.
 */

const RUBLE_SUFFIX = " ₽"; // NBSP + ₽ — keeps the suffix glued to the number.

/**
 * Format a number as a ru-RU RUB amount with NBSP thousand separators
 * and a "₽" suffix.
 *
 * `value` MUST be finite. NaN / Infinity return `"0 ₽"` so the UI
 * never renders the JS string `"NaN ₽"` — defensive guard for the rare
 * cases where upstream divisions produce non-finite numbers.
 */
export function formatRub(value: number): string {
  if (!Number.isFinite(value)) {
    return `0${RUBLE_SUFFIX}`;
  }

  // Integer fast-path — render without decimals to match mockup typography.
  if (Number.isInteger(value)) {
    const formatted = value.toLocaleString("ru-RU", {
      maximumFractionDigits: 0,
    });
    return `${formatted}${RUBLE_SUFFIX}`;
  }

  // Fractional path — always render exactly 2 decimal places ("999 999,99 ₽")
  // so kopek-shares don't lose precision in display.
  const formatted = value.toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${formatted}${RUBLE_SUFFIX}`;
}
