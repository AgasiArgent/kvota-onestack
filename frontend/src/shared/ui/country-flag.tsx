/**
 * CountryFlag — renders a flag emoji for an ISO 3166-1 alpha-2 code.
 *
 * Uses Unicode Regional Indicator Symbols (no flag font required).
 * Flags are the one allowed "emoji as content" case per design-system.md
 * (all other decorative icons go through lucide-react).
 *
 * Used by: LocationChip, workspace tables, admin routing patterns.
 */

interface CountryFlagProps {
  /** ISO 3166-1 alpha-2 code, e.g. "RU", "CN", "TR". Case-insensitive. */
  iso2: string;
  /**
   * Accessible label. If omitted, the flag is treated as decorative
   * (aria-hidden). Provide a country name when the flag is the only
   * country indicator (no adjacent text label).
   */
  aria?: string;
  className?: string;
}

const A_CODE_POINT = 0x1f1e6; // Regional Indicator Symbol Letter A
const LETTER_A_CODE_POINT = "A".charCodeAt(0);

function isoToFlag(iso2: string): string {
  const upper = iso2.trim().toUpperCase();
  if (upper.length !== 2 || !/^[A-Z]{2}$/.test(upper)) return "";
  return (
    String.fromCodePoint(A_CODE_POINT + (upper.charCodeAt(0) - LETTER_A_CODE_POINT)) +
    String.fromCodePoint(A_CODE_POINT + (upper.charCodeAt(1) - LETTER_A_CODE_POINT))
  );
}

export function CountryFlag({ iso2, aria, className }: CountryFlagProps) {
  const flag = isoToFlag(iso2);
  if (!flag) return null;
  return (
    <span
      className={className}
      role={aria ? "img" : undefined}
      aria-label={aria}
      aria-hidden={aria ? undefined : true}
      // Emoji presentation selector ensures colored rendering on win/linux
      style={{ fontVariantEmoji: "emoji" }}
    >
      {flag}
    </span>
  );
}
