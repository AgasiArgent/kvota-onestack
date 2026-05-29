import { describe, expect, it } from "vitest";
import {
  buildHistoricalRateMap,
  convertOnDate,
  convertToUsdOnDate,
  pickRateOnOrBefore,
  sumInvoiceLinesInUsd,
  type FxRateRow,
} from "../historical-fx";

// Three snapshots per currency simulating CBR fetch history.
// USD strengthens RUB from 90 → 95 → 100 over Jan/Feb/Mar 2026.
const rateRows: FxRateRow[] = [
  { from_currency: "USD", rate: 90, fetched_at: "2026-01-15T00:00:00Z" },
  { from_currency: "USD", rate: 95, fetched_at: "2026-02-15T00:00:00Z" },
  { from_currency: "USD", rate: 100, fetched_at: "2026-03-15T00:00:00Z" },
  { from_currency: "EUR", rate: 100, fetched_at: "2026-01-15T00:00:00Z" },
  { from_currency: "EUR", rate: 110, fetched_at: "2026-03-15T00:00:00Z" },
  { from_currency: "CNY", rate: 12, fetched_at: "2026-02-15T00:00:00Z" },
];

describe("buildHistoricalRateMap", () => {
  it("groups by uppercase currency and sorts DESC by fetched_at", () => {
    const m = buildHistoricalRateMap(rateRows);
    const usd = m.get("USD");
    expect(usd).toBeDefined();
    expect(usd!.map((r) => r.fetched_at)).toEqual([
      "2026-03-15T00:00:00Z",
      "2026-02-15T00:00:00Z",
      "2026-01-15T00:00:00Z",
    ]);
  });

  it("normalizes lowercase currency codes", () => {
    const m = buildHistoricalRateMap([
      { from_currency: "usd", rate: 90, fetched_at: "2026-01-01T00:00:00Z" },
    ]);
    expect(m.has("USD")).toBe(true);
  });

  it("drops non-finite and non-positive rates", () => {
    const m = buildHistoricalRateMap([
      { from_currency: "JPY", rate: Number.NaN, fetched_at: "2026-01-01T00:00:00Z" },
      { from_currency: "JPY", rate: 0, fetched_at: "2026-01-02T00:00:00Z" },
      { from_currency: "JPY", rate: -1, fetched_at: "2026-01-03T00:00:00Z" },
    ]);
    expect(m.has("JPY")).toBe(false);
  });
});

describe("pickRateOnOrBefore", () => {
  const rates = buildHistoricalRateMap(rateRows);

  it("picks the most recent rate with fetched_at <= asOf", () => {
    // 2026-02-20 is between Feb 15 and Mar 15 — should pick Feb 15 (95).
    expect(pickRateOnOrBefore(rates, "USD", "2026-02-20T00:00:00Z")).toBe(95);
  });

  it("picks the exact-match rate when asOf equals a fetched_at", () => {
    expect(pickRateOnOrBefore(rates, "USD", "2026-02-15T00:00:00Z")).toBe(95);
  });

  it("falls back to the earliest available rate when asOf precedes all data", () => {
    // КПП predating our FX archive — fall back to oldest (Jan 15, 90) so the
    // total isn't silently dropped.
    expect(pickRateOnOrBefore(rates, "USD", "2025-12-01T00:00:00Z")).toBe(90);
  });

  it("returns identity for RUB regardless of date", () => {
    expect(pickRateOnOrBefore(rates, "RUB", "2026-02-20T00:00:00Z")).toBe(1);
  });

  it("returns null for currency with no rates", () => {
    expect(pickRateOnOrBefore(rates, "JPY", "2026-02-20T00:00:00Z")).toBeNull();
  });
});

describe("convertOnDate", () => {
  const rates = buildHistoricalRateMap(rateRows);

  it("returns identity when from === to (case-insensitive)", () => {
    expect(convertOnDate(123, "EUR", "EUR", "2026-02-20T00:00:00Z", rates)).toBe(
      123,
    );
    expect(convertOnDate(123, "eur", "EUR", "2026-02-20T00:00:00Z", rates)).toBe(
      123,
    );
  });

  it("converts EUR to USD via RUB on the historical date", () => {
    // On 2026-02-20: EUR=100 (Jan, no Feb update), USD=95. 10*100/95 ≈ 10.526
    expect(
      convertOnDate(10, "EUR", "USD", "2026-02-20T00:00:00Z", rates),
    ).toBeCloseTo(10.5263, 3);
  });

  it("converts USD to EUR (inverse direction) on the historical date", () => {
    // On 2026-03-20: USD=100, EUR=110. 11 USD * 100 / 110 = 10 EUR
    expect(
      convertOnDate(11, "USD", "EUR", "2026-03-20T00:00:00Z", rates),
    ).toBeCloseTo(10, 6);
  });

  it("converts EUR to RUB using the source leg only (dst RUB = 1)", () => {
    // On 2026-03-20: EUR=110. 10 EUR * 110 / 1 = 1100 RUB
    expect(
      convertOnDate(10, "EUR", "RUB", "2026-03-20T00:00:00Z", rates),
    ).toBeCloseTo(1100, 6);
  });

  it("converts RUB to USD by dividing by the USD leg (src RUB = 1)", () => {
    // On 2026-02-20: USD=95. 950 RUB / 95 = 10 USD
    expect(
      convertOnDate(950, "RUB", "USD", "2026-02-20T00:00:00Z", rates),
    ).toBeCloseTo(10, 6);
  });

  it("uses the date-appropriate rate, not the latest", () => {
    // On 2026-01-20: EUR=100, USD=90. 10*100/90 ≈ 11.111
    expect(
      convertOnDate(10, "EUR", "USD", "2026-01-20T00:00:00Z", rates),
    ).toBeCloseTo(11.111, 2);
  });

  it("returns null when the source currency has no rates", () => {
    expect(
      convertOnDate(10, "JPY", "USD", "2026-02-20T00:00:00Z", rates),
    ).toBeNull();
  });

  it("returns null when the destination currency has no rates", () => {
    expect(
      convertOnDate(10, "USD", "JPY", "2026-02-20T00:00:00Z", rates),
    ).toBeNull();
  });

  it("returns 0 for zero amount regardless of rate availability", () => {
    expect(convertOnDate(0, "JPY", "GBP", "2026-02-20T00:00:00Z", rates)).toBe(
      0,
    );
  });

  it("returns null for non-finite amounts", () => {
    expect(
      convertOnDate(Number.NaN, "EUR", "USD", "2026-02-20T00:00:00Z", rates),
    ).toBeNull();
  });
});

describe("convertToUsdOnDate", () => {
  const rates = buildHistoricalRateMap(rateRows);

  it("returns identity for USD source", () => {
    expect(convertToUsdOnDate(123, "USD", "2026-02-20T00:00:00Z", rates)).toBe(
      123,
    );
  });

  it("converts EUR to USD via RUB on the historical date", () => {
    // On 2026-02-20: EUR rate is 100 (Jan 15, no Feb update), USD rate is 95.
    // 10 EUR * 100 / 95 ≈ 10.526
    const result = convertToUsdOnDate(10, "EUR", "2026-02-20T00:00:00Z", rates);
    expect(result).toBeCloseTo(10.5263, 3);
  });

  it("uses the date-appropriate rate (not the latest)", () => {
    // On 2026-03-20: EUR is 110, USD is 100.
    // 10 EUR * 110 / 100 = 11.0
    expect(
      convertToUsdOnDate(10, "EUR", "2026-03-20T00:00:00Z", rates),
    ).toBeCloseTo(11.0, 5);
    // On 2026-01-20: EUR is 100, USD is 90.
    // 10 EUR * 100 / 90 ≈ 11.111
    expect(
      convertToUsdOnDate(10, "EUR", "2026-01-20T00:00:00Z", rates),
    ).toBeCloseTo(11.111, 2);
  });

  it("converts RUB to USD by dividing by USD rate on that date", () => {
    // On 2026-02-20: USD rate is 95. 950 RUB / 95 = 10 USD.
    expect(
      convertToUsdOnDate(950, "RUB", "2026-02-20T00:00:00Z", rates),
    ).toBeCloseTo(10, 6);
  });

  it("returns null when the source currency has no rates", () => {
    expect(
      convertToUsdOnDate(10, "JPY", "2026-02-20T00:00:00Z", rates),
    ).toBeNull();
  });

  it("returns 0 for zero amount even with missing source rate", () => {
    expect(convertToUsdOnDate(0, "JPY", "2026-02-20T00:00:00Z", rates)).toBe(0);
  });

  it("returns null for non-finite amounts", () => {
    expect(
      convertToUsdOnDate(Number.NaN, "USD", "2026-02-20T00:00:00Z", rates),
    ).toBeNull();
  });

  it("treats currency codes case-insensitively", () => {
    expect(
      convertToUsdOnDate(10, "usd", "2026-02-20T00:00:00Z", rates),
    ).toBe(10);
  });
});

describe("sumInvoiceLinesInUsd", () => {
  const rates = buildHistoricalRateMap(rateRows);

  it("sums mixed-currency, mixed-date lines into USD", () => {
    const result = sumInvoiceLinesInUsd(
      [
        // 100 USD on any date → 100 USD
        { amount: 100, currency: "USD", asOf: "2026-02-20T00:00:00Z" },
        // 950 RUB on 2026-02-20 (USD=95) → 10 USD
        { amount: 950, currency: "RUB", asOf: "2026-02-20T00:00:00Z" },
        // 10 EUR on 2026-03-20 (EUR=110, USD=100) → 11 USD
        { amount: 10, currency: "EUR", asOf: "2026-03-20T00:00:00Z" },
      ],
      rates,
    );
    expect(result.totalUsd).toBeCloseTo(121, 4);
    expect(result.missing).toEqual([]);
  });

  it("excludes lines whose currency is missing and reports them", () => {
    const result = sumInvoiceLinesInUsd(
      [
        { amount: 100, currency: "USD", asOf: "2026-02-20T00:00:00Z" },
        { amount: 5000, currency: "JPY", asOf: "2026-02-20T00:00:00Z" },
        { amount: 200, currency: "GBP", asOf: "2026-02-20T00:00:00Z" },
      ],
      rates,
    );
    expect(result.totalUsd).toBe(100);
    expect(result.missing).toEqual(["GBP", "JPY"]);
  });

  it("returns zero totals and empty missing for an empty list", () => {
    const result = sumInvoiceLinesInUsd([], rates);
    expect(result.totalUsd).toBe(0);
    expect(result.missing).toEqual([]);
  });

  it("looks up FX per line independently (no global asOf)", () => {
    // Same 10 EUR amount on two different dates produces two different
    // USD figures — verifies the per-line lookup.
    const a = sumInvoiceLinesInUsd(
      [{ amount: 10, currency: "EUR", asOf: "2026-01-20T00:00:00Z" }],
      rates,
    );
    const b = sumInvoiceLinesInUsd(
      [{ amount: 10, currency: "EUR", asOf: "2026-03-20T00:00:00Z" }],
      rates,
    );
    expect(a.totalUsd).not.toBe(b.totalUsd);
    expect(a.totalUsd).toBeCloseTo(11.111, 2); // 100/90
    expect(b.totalUsd).toBeCloseTo(11.0, 5); // 110/100
  });
});
