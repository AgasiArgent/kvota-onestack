import { describe, expect, it } from "vitest";
import { convertCurrency, sumInCurrency } from "../fx-convert";

const ratesToRub = {
  USD: 90,
  EUR: 100,
  CNY: 12,
};

describe("convertCurrency", () => {
  it("returns identity for same source and target", () => {
    expect(convertCurrency(123, "USD", "USD", ratesToRub)).toBe(123);
    expect(convertCurrency(50, "RUB", "RUB", ratesToRub)).toBe(50);
  });

  it("converts foreign currency to RUB via rate map", () => {
    // 10 USD * 90 RUB/USD = 900 RUB
    expect(convertCurrency(10, "USD", "RUB", ratesToRub)).toBe(900);
    // 5 EUR * 100 RUB/EUR = 500 RUB
    expect(convertCurrency(5, "EUR", "RUB", ratesToRub)).toBe(500);
  });

  it("converts RUB to a foreign currency", () => {
    // 900 RUB / 90 RUB/USD = 10 USD
    expect(convertCurrency(900, "RUB", "USD", ratesToRub)).toBe(10);
  });

  it("converts foreign-to-foreign through implicit RUB", () => {
    // 10 USD = 900 RUB ; 900 / 100 = 9 EUR
    expect(convertCurrency(10, "USD", "EUR", ratesToRub)).toBe(9);
  });

  it("treats currency codes case-insensitively", () => {
    expect(convertCurrency(10, "usd", "rub", ratesToRub)).toBe(900);
  });

  it("returns null when source rate is unavailable", () => {
    expect(convertCurrency(10, "JPY", "RUB", ratesToRub)).toBeNull();
  });

  it("returns null when target rate is unavailable", () => {
    expect(convertCurrency(900, "RUB", "JPY", ratesToRub)).toBeNull();
  });

  it("returns 0 for zero amount even with missing rate", () => {
    // zero is the safe sentinel — caller doesn't need to special-case it.
    expect(convertCurrency(0, "JPY", "RUB", ratesToRub)).toBe(0);
  });

  it("returns null for non-finite amounts", () => {
    expect(convertCurrency(Number.NaN, "USD", "RUB", ratesToRub)).toBeNull();
    expect(
      convertCurrency(Number.POSITIVE_INFINITY, "USD", "RUB", ratesToRub),
    ).toBeNull();
  });
});

describe("sumInCurrency", () => {
  it("sums identical-currency entries directly", () => {
    const result = sumInCurrency(
      [
        { amount: 100, currency: "RUB" },
        { amount: 50, currency: "RUB" },
      ],
      "RUB",
      ratesToRub,
    );
    expect(result.total).toBe(150);
    expect(result.missing).toEqual([]);
  });

  it("converts mixed currencies into the target", () => {
    const result = sumInCurrency(
      [
        { amount: 10, currency: "USD" }, // 900 RUB
        { amount: 5, currency: "EUR" }, // 500 RUB
        { amount: 100, currency: "RUB" }, // 100 RUB
      ],
      "RUB",
      ratesToRub,
    );
    expect(result.total).toBe(1500);
    expect(result.missing).toEqual([]);
  });

  it("excludes entries with missing rates and reports them", () => {
    const result = sumInCurrency(
      [
        { amount: 10, currency: "USD" },
        { amount: 5, currency: "JPY" },
        { amount: 100, currency: "GBP" },
      ],
      "RUB",
      ratesToRub,
    );
    expect(result.total).toBe(900); // only USD converted
    expect(result.missing).toEqual(["GBP", "JPY"]);
  });
});
