import { describe, it, expect } from "vitest";
import {
  SUPPORTED_CURRENCIES,
  CURRENCY_LABELS,
  isSupportedCurrency,
} from "../currencies";

describe("SUPPORTED_CURRENCIES", () => {
  it("contains exactly 10 entries", () => {
    expect(SUPPORTED_CURRENCIES.length).toBe(10);
  });

  it("contains all 10 expected codes in backend sync order", () => {
    expect(SUPPORTED_CURRENCIES).toEqual([
      "USD",
      "EUR",
      "RUB",
      "CNY",
      "TRY",
      "AED",
      "KZT",
      "JPY",
      "GBP",
      "CHF",
    ]);
  });
});

describe("CURRENCY_LABELS", () => {
  it("has a non-empty label for every supported currency", () => {
    for (const code of SUPPORTED_CURRENCIES) {
      expect(CURRENCY_LABELS[code]).toBeTruthy();
      expect(typeof CURRENCY_LABELS[code]).toBe("string");
    }
  });
});

describe("isSupportedCurrency", () => {
  it("returns true for an exact uppercase code", () => {
    expect(isSupportedCurrency("USD")).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(isSupportedCurrency("usd")).toBe(true);
  });

  it("returns false for an unknown code", () => {
    expect(isSupportedCurrency("XXX")).toBe(false);
  });

  it("returns false for an empty string", () => {
    expect(isSupportedCurrency("")).toBe(false);
  });

  it("returns false for null", () => {
    expect(isSupportedCurrency(null)).toBe(false);
  });

  it("returns false for undefined", () => {
    expect(isSupportedCurrency(undefined)).toBe(false);
  });
});
