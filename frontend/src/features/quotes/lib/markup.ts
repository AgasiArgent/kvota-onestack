/**
 * Markup validation — hard stop at 5% (Testing 2 row 47).
 *
 * Single source of truth for the FE-side gate. Mirrors the backend guard
 * in api/quotes.py::calculate_quote (MARKUP_TOO_LOW). Empty / non-numeric
 * strings are treated as "not yet set" (not invalid) so users editing the
 * input don't see a flash of red on focus before typing.
 */
export const MARKUP_MIN_PERCENT = 5;

export const MARKUP_BELOW_MIN_ERROR = "Наценка не может быть меньше 5%";

export function isMarkupBelowMinimum(raw: string | null | undefined): boolean {
  if (raw == null) return false;
  const trimmed = String(raw).trim();
  if (trimmed === "") return false;
  const n = Number(trimmed);
  if (!Number.isFinite(n)) return false;
  return n < MARKUP_MIN_PERCENT;
}
