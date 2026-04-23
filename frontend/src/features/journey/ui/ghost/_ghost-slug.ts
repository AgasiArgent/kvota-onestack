/**
 * Slug derivation + validation for ghost nodes (`node_id = ghost:<slug>`).
 *
 * Requirement 7.2 says the slug must be URL-safe and unique; the DB UNIQUE
 * constraint is authoritative, but the frontend pre-validates to avoid
 * obvious collisions and to give instant feedback while typing.
 *
 * Input policy:
 *   - Latin letters, digits, and whitespace → kept (lowercased).
 *   - Cyrillic letters → transliterated via the minimal table below.
 *   - Everything else → separator.
 *
 * The Cyrillic table is intentionally minimal — covering Russian letters
 * used in the OneStack UI. It is NOT a full ISO-9 transliteration:
 *
 *   TECH DEBT: a single-letter Russian title like "Й" will transliterate
 *   to "y"; complex romanisations (e.g. GOST 7.79) are out of scope. If
 *   product surfaces German / French / etc. titles, extend the table or
 *   pull in a proper `slugify` dependency.
 */

const CYRILLIC_TO_LATIN: Record<string, string> = {
  а: "a",
  б: "b",
  в: "v",
  г: "g",
  д: "d",
  е: "e",
  ё: "e",
  ж: "zh",
  з: "z",
  и: "i",
  й: "y",
  к: "k",
  л: "l",
  м: "m",
  н: "n",
  о: "o",
  п: "p",
  р: "r",
  с: "s",
  т: "t",
  у: "u",
  ф: "f",
  х: "h",
  ц: "c",
  ч: "ch",
  ш: "sh",
  щ: "sch",
  ъ: "",
  ы: "y",
  ь: "",
  э: "e",
  ю: "yu",
  я: "ya",
};

function transliterateChar(ch: string): string {
  const lower = ch.toLowerCase();
  if (CYRILLIC_TO_LATIN[lower] !== undefined) return CYRILLIC_TO_LATIN[lower];
  // Keep latin alphanumerics as-is (lowercased). Everything else becomes a
  // separator; the caller collapses separators into single dashes.
  if (/[a-z0-9]/.test(lower)) return lower;
  return " ";
}

/**
 * Deterministically derive a slug from a human title. Pure, no side effects.
 */
export function deriveGhostSlug(title: string): string {
  const transliterated = Array.from(title.trim())
    .map(transliterateChar)
    .join("");
  return transliterated
    .split(/[^a-z0-9]+/)
    .filter(Boolean)
    .join("-");
}

/**
 * Strict kebab-case validator. Matches the DB's expected format:
 *   - lowercase latin letters and digits
 *   - single-dash separators
 *   - alphanum start and end
 *   - minimum length 1
 */
const SLUG_PATTERN = /^[a-z0-9](?:[a-z0-9]|-(?=[a-z0-9]))*$/;

export function validateGhostSlug(slug: string): boolean {
  if (slug.length === 0) return false;
  return SLUG_PATTERN.test(slug);
}
