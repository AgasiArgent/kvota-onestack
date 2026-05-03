import { describe, it, expect } from "vitest";

import {
  filterOksmCountries,
  computeNextFocusedIndex,
} from "../ui/country-dropdown";
import type { OksmCountry } from "../api/fetch-countries";

const SAMPLE: OksmCountry[] = [
  { oksm_digital: 643, iso_alpha2: "RU", name_ru: "Россия", is_unfriendly: false },
  { oksm_digital: 156, iso_alpha2: "CN", name_ru: "Китай", is_unfriendly: false },
  { oksm_digital: 840, iso_alpha2: "US", name_ru: "США", is_unfriendly: true },
  { oksm_digital: 276, iso_alpha2: "DE", name_ru: "Германия", is_unfriendly: true },
];

describe("filterOksmCountries", () => {
  it("returns full list for empty query", () => {
    expect(filterOksmCountries(SAMPLE, "")).toHaveLength(4);
  });

  it("returns full list for whitespace-only query", () => {
    expect(filterOksmCountries(SAMPLE, "   ")).toHaveLength(4);
  });

  it("matches by name_ru substring case-insensitive", () => {
    const result = filterOksmCountries(SAMPLE, "рос");
    expect(result).toHaveLength(1);
    expect(result[0].iso_alpha2).toBe("RU");
  });

  it("matches by iso_alpha2", () => {
    const result = filterOksmCountries(SAMPLE, "cn");
    expect(result).toHaveLength(1);
    expect(result[0].name_ru).toBe("Китай");
  });

  it("matches by oksm_digital substring", () => {
    const result = filterOksmCountries(SAMPLE, "840");
    expect(result).toHaveLength(1);
    expect(result[0].iso_alpha2).toBe("US");
  });

  it("returns empty list when nothing matches", () => {
    expect(filterOksmCountries(SAMPLE, "несуществующая")).toHaveLength(0);
  });
});

describe("computeNextFocusedIndex", () => {
  it("returns -1 for empty list", () => {
    expect(computeNextFocusedIndex(0, "down", 0)).toBe(-1);
    expect(computeNextFocusedIndex(0, "up", 0)).toBe(-1);
  });

  it("ArrowDown from -1 lands on 0", () => {
    expect(computeNextFocusedIndex(-1, "down", 5)).toBe(0);
  });

  it("ArrowUp from -1 wraps to last", () => {
    expect(computeNextFocusedIndex(-1, "up", 5)).toBe(4);
  });

  it("ArrowDown wraps from last to 0", () => {
    expect(computeNextFocusedIndex(4, "down", 5)).toBe(0);
  });

  it("ArrowUp wraps from 0 to last", () => {
    expect(computeNextFocusedIndex(0, "up", 5)).toBe(4);
  });

  it("clamps out-of-range starting indices", () => {
    expect(computeNextFocusedIndex(99, "down", 5)).toBe(0);
    expect(computeNextFocusedIndex(-99, "down", 5)).toBe(0);
  });
});
