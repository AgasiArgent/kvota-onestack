/**
 * Date formatting helpers for the customs-history feature (Phase A Req 10).
 *
 * Pure functions — no DOM dependencies. Tested in `format-date.test.ts`.
 */

/** Format ISO timestamp to Russian DD.MM.YYYY convention. */
export function formatDateRussian(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const day = String(d.getDate()).padStart(2, "0");
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const year = d.getFullYear();
    return `${day}.${month}.${year}`;
  } catch {
    return "";
  }
}
