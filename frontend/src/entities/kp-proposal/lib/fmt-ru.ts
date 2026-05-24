/**
 * Format a numeric-ish value with Russian locale conventions.
 *
 * Mirrors `services/kp_export.py:_fmt_ru`:
 * - Strips ASCII / non-breaking / narrow no-break spaces from the input.
 * - Accepts comma OR dot as decimal mark.
 * - Returns the raw input verbatim when parsing fails (REQ-3.4 — never
 *   crash the renderer on hand-typed values like "по запросу").
 * - Empty / null / undefined → empty string.
 *
 * We format manually instead of relying on Intl.NumberFormat("ru-RU")
 * because Node's Intl emits U+00A0 (regular non-breaking space) as the
 * thousand separator, while the Python backend emits U+202F (narrow
 * no-break space) per REQ-3.3. Both look visually identical but they
 * differ byte-for-byte, which would make the preview and PDF disagree
 * on otherwise-identical input.
 */

const NNBSP = " ";

export function fmtRu(value: unknown): string {
  if (value === null || value === undefined) return "";
  const raw = String(value).trim();
  if (raw === "") return "";

  // Strip every space flavour the user may have pasted in. The regex
  // `\s` already covers ASCII, NBSP and NNBSP, but we keep explicit
  // replaces for clarity at the parity boundary with the Python helper.
  const cleaned = raw
    .replace(/\s/g, "")
    .replace(/ /g, "")
    .replace(/ /g, "")
    .replace(",", ".");

  const parsed = Number(cleaned);
  if (!Number.isFinite(parsed)) return raw;

  const sign = parsed < 0 ? "-" : "";
  const abs = Math.abs(parsed);

  // Split into integer + fractional parts, preserve up to 2 fraction digits
  // and strip trailing zeros (matches toLocaleString maximumFractionDigits:2
  // behaviour the Python helper also implements).
  const fixed = abs.toFixed(2);
  const [intPartRaw, fracRaw] = fixed.split(".");
  const fracPart = (fracRaw ?? "").replace(/0+$/, "");

  // Group integer part in 3-digit blocks from the right with NNBSP.
  const grouped = intPartRaw.replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP);

  return fracPart ? `${sign}${grouped},${fracPart}` : `${sign}${grouped}`;
}
