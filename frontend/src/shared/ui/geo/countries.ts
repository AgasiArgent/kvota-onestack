/**
 * Static bilingual country data backed by the runtime's ICU tables.
 *
 * The list is built exactly once at module load from `Intl.DisplayNames`
 * (Russian + English), keeping the shared Geo module free of per-locale
 * maintenance. Both lookup helpers (`findCountryByCode`, `findCountryByName`)
 * are tolerant of null/undefined input so consumers can pass raw DB values
 * without pre-checking.
 *
 * Design notes:
 *
 * - `Intl.supportedValuesOf("region")` is an active ECMA-402 proposal that
 *   V8/Node has not yet implemented (Node 25 / V8 13.x still throws
 *   "Invalid key: region"). We therefore enumerate every alpha-2 pair
 *   AA..ZZ and filter to values that `Intl.DisplayNames` actually resolves
 *   (i.e., returns a string different from the code itself). When V8 ships
 *   the proposal, the preferred path kicks in automatically.
 * - If `Intl.DisplayNames` itself is missing, the list is empty and the
 *   picker renders an empty state rather than throwing (REQ 1.11).
 */

export interface Country {
  readonly code: string;
  readonly nameRu: string;
  readonly nameEn: string;
}

function buildCountries(): readonly Country[] {
  if (typeof Intl === "undefined" || typeof Intl.DisplayNames !== "function") {
    return [];
  }

  let displayRu: Intl.DisplayNames;
  let displayEn: Intl.DisplayNames;
  try {
    displayRu = new Intl.DisplayNames(["ru"], { type: "region" });
    displayEn = new Intl.DisplayNames(["en"], { type: "region" });
  } catch {
    return [];
  }

  const codes = enumerateRegionCodes();
  const countries: Country[] = [];
  for (const code of codes) {
    // Skip deprecated ISO codes that ICU still resolves to a current country
    // name (e.g. "DD" = historical East Germany → "Germany", "SU" → "Russia",
    // "YU" → "Serbia"). Leaving them in would produce duplicate entries with
    // the same display name but different codes, confusing both the search
    // filter and the `findCountryByName` helper.
    if (!isCanonicalRegionCode(code)) {
      continue;
    }

    const nameRu = safeDisplay(displayRu, code);
    const nameEn = safeDisplay(displayEn, code);
    // DisplayNames returns the input code unchanged for non-regions; skip those.
    if (!nameRu || !nameEn || nameRu === code || nameEn === code) {
      continue;
    }
    countries.push({ code, nameRu, nameEn });
  }

  countries.sort((a, b) => a.nameRu.localeCompare(b.nameRu, "ru"));
  return countries;
}

/**
 * Returns true when `code` is the canonical form of itself — i.e., ICU's
 * locale canonicalization does not rewrite it to a different region code.
 * Used to drop deprecated ISO 3166-1 codes from the list.
 */
function isCanonicalRegionCode(code: string): boolean {
  try {
    const canonical = Intl.getCanonicalLocales(`und-${code}`)[0];
    // Format is `und-XX`; extract the region part after the first dash.
    const region = canonical.split("-")[1];
    return region === code;
  } catch {
    return false;
  }
}

function enumerateRegionCodes(): readonly string[] {
  // Preferred path: `Intl.supportedValuesOf("region")` when the runtime
  // ships the ECMA-402 proposal. Guarded via `as unknown as` so older lib
  // targets still type-check.
  const intlAny = Intl as unknown as {
    supportedValuesOf?: (key: string) => readonly string[];
  };
  if (typeof intlAny.supportedValuesOf === "function") {
    try {
      const values = intlAny.supportedValuesOf("region");
      const filtered = values.filter((v) => /^[A-Z]{2}$/.test(v));
      if (filtered.length > 0) {
        return filtered;
      }
    } catch {
      // Fall through to enumeration. V8 in Node 25 throws "Invalid key: region".
    }
  }

  // Fallback: exhaustively enumerate every AA..ZZ pair and let the
  // `buildCountries` loop filter out codes that ICU does not recognise.
  const codes: string[] = [];
  for (let a = 65; a <= 90; a++) {
    for (let b = 65; b <= 90; b++) {
      codes.push(String.fromCharCode(a) + String.fromCharCode(b));
    }
  }
  return codes;
}

function safeDisplay(dn: Intl.DisplayNames, code: string): string {
  try {
    return dn.of(code) ?? "";
  } catch {
    return "";
  }
}

export const COUNTRIES: readonly Country[] = buildCountries();

/**
 * Resolve an ISO 3166-1 alpha-2 code to its bilingual record.
 * Case-insensitive, whitespace-tolerant. Returns undefined for null/empty.
 */
export function findCountryByCode(
  code: string | null | undefined,
): Country | undefined {
  if (code == null) return undefined;
  const normalized = code.trim().toUpperCase();
  if (normalized.length === 0) return undefined;
  return COUNTRIES.find((c) => c.code === normalized);
}

/**
 * Resolve a human-readable country name to its bilingual record.
 * Case-insensitive, whitespace-tolerant. Matches against the specified
 * locale's name field exclusively (default: "ru"). Returns undefined when
 * no match is found — callers use this to detect legacy free-text values
 * that do not round-trip cleanly (REQ 1.12, 11.5).
 */
export function findCountryByName(
  name: string | null | undefined,
  locale: "ru" | "en" = "ru",
): Country | undefined {
  if (name == null) return undefined;
  const normalized = name.trim().toLowerCase();
  if (normalized.length === 0) return undefined;
  const field = locale === "en" ? "nameEn" : "nameRu";
  return COUNTRIES.find((c) => c[field].toLowerCase() === normalized);
}
