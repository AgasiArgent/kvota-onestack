/**
 * Format a number with RU locale, always two fraction digits.
 * Mirrors the FastHTML `fmt` helper (`f"{value:,.2f}"`).
 */
export function formatAmount(value: number): string {
  return value.toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Format a percentage with one fraction digit, e.g. `12.3%`. */
export function formatPercent(value: number): string {
  return `${value.toLocaleString("ru-RU", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

/**
 * Compute the percent of revenue for a line item. Guards against
 * zero-division — returns 0 when revenue is not positive.
 */
export function pctOfRevenue(value: number, revenue: number): number {
  if (revenue <= 0) return 0;
  return (value / revenue) * 100;
}
