import { describe, it, expect } from "vitest";

import {
  COUNTRIES,
  findCountryByCode,
  findCountryByName,
} from "../countries";

describe("COUNTRIES constant", () => {
  it("contains a realistic number of ISO 3166-1 alpha-2 entries", () => {
    // ICU data exposes ~250 countries; we accept anything above 200 to stay
    // resilient to ICU version drift between environments.
    expect(COUNTRIES.length).toBeGreaterThan(200);
  });

  it("has a valid alpha-2 code on every entry", () => {
    for (const country of COUNTRIES) {
      expect(country.code).toMatch(/^[A-Z]{2}$/);
    }
  });

  it("has non-empty Russian and English names on every entry", () => {
    for (const country of COUNTRIES) {
      expect(country.nameRu.length).toBeGreaterThan(0);
      expect(country.nameEn.length).toBeGreaterThan(0);
    }
  });

  it("is sorted by Russian name via localeCompare", () => {
    const expected = [...COUNTRIES]
      .map((c) => c.nameRu)
      .sort((a, b) => a.localeCompare(b, "ru"));
    const actual = COUNTRIES.map((c) => c.nameRu);
    expect(actual).toEqual(expected);
  });

  it("includes core ISO countries with expected Russian labels", () => {
    const de = COUNTRIES.find((c) => c.code === "DE");
    const ru = COUNTRIES.find((c) => c.code === "RU");
    const us = COUNTRIES.find((c) => c.code === "US");
    expect(de?.nameRu).toBe("Германия");
    expect(de?.nameEn).toBe("Germany");
    expect(ru?.nameRu).toBe("Россия");
    expect(us?.nameEn).toBe("United States");
  });
});

describe("findCountryByCode", () => {
  it("returns the matching country for an uppercase ISO code", () => {
    const result = findCountryByCode("DE");
    expect(result?.nameRu).toBe("Германия");
  });

  it("is case-insensitive", () => {
    const lower = findCountryByCode("de");
    const upper = findCountryByCode("DE");
    expect(lower).toBe(upper);
  });

  it("trims whitespace", () => {
    const result = findCountryByCode("  DE  ");
    expect(result?.code).toBe("DE");
  });

  it("returns undefined for null", () => {
    expect(findCountryByCode(null)).toBeUndefined();
  });

  it("returns undefined for undefined", () => {
    expect(findCountryByCode(undefined)).toBeUndefined();
  });

  it("returns undefined for empty string", () => {
    expect(findCountryByCode("")).toBeUndefined();
  });

  it("returns undefined for whitespace-only string", () => {
    expect(findCountryByCode("   ")).toBeUndefined();
  });

  it("returns undefined for an unknown / non-ISO code", () => {
    // "XQ" is not assigned in ISO 3166-1 and not recognised by ICU's DisplayNames.
    expect(findCountryByCode("XQ")).toBeUndefined();
  });
});

describe("findCountryByName", () => {
  it("finds by Russian name by default", () => {
    const result = findCountryByName("Германия");
    expect(result?.code).toBe("DE");
  });

  it("finds by Russian name with explicit locale", () => {
    const result = findCountryByName("Россия", "ru");
    expect(result?.code).toBe("RU");
  });

  it("finds by English name when locale is 'en'", () => {
    const result = findCountryByName("Germany", "en");
    expect(result?.code).toBe("DE");
  });

  it("is case-insensitive (Russian)", () => {
    const result = findCountryByName("ГЕРМАНИЯ");
    expect(result?.code).toBe("DE");
  });

  it("is case-insensitive (English)", () => {
    const result = findCountryByName("GERMANY", "en");
    expect(result?.code).toBe("DE");
  });

  it("trims surrounding whitespace", () => {
    const result = findCountryByName("  Германия  ");
    expect(result?.code).toBe("DE");
  });

  it("returns undefined for an unknown name", () => {
    expect(findCountryByName("Атлантида")).toBeUndefined();
  });

  it("returns undefined for null", () => {
    expect(findCountryByName(null)).toBeUndefined();
  });

  it("returns undefined for undefined", () => {
    expect(findCountryByName(undefined)).toBeUndefined();
  });

  it("returns undefined for empty string", () => {
    expect(findCountryByName("")).toBeUndefined();
  });

  it("does NOT match the English name when locale is 'ru'", () => {
    // "Germany" is the English name; default locale is "ru", so no match.
    expect(findCountryByName("Germany", "ru")).toBeUndefined();
  });

  it("does NOT match the Russian name when locale is 'en'", () => {
    expect(findCountryByName("Германия", "en")).toBeUndefined();
  });
});
