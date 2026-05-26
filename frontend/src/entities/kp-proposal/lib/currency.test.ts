/**
 * Frontend currency table tests — mirror of the Python
 * `test_kp_export_html.py::TestCurrencyRendering` suite, restricted to the
 * formatting helpers since the preview itself is exercised by the dom test.
 *
 * The Python and TypeScript tables MUST stay in sync — divergence shows up
 * as a preview vs. exported PDF mismatch. If a code is added on one side,
 * add it on the other in the same PR.
 */

import { describe, it, expect } from "vitest";

import {
  CURRENCIES,
  currencyEntry,
  currencySymbol,
  headlineSuffix,
} from "./currency";

describe("currencySymbol", () => {
  it("returns the configured symbol for every supported code", () => {
    expect(currencySymbol("RUB")).toBe("₽");
    expect(currencySymbol("USD")).toBe("$");
    expect(currencySymbol("EUR")).toBe("€");
    expect(currencySymbol("CNY")).toBe("¥");
    expect(currencySymbol("AED")).toBe("AED");
    expect(currencySymbol("TRY")).toBe("₺");
  });

  it("falls back to RUB for unknown codes", () => {
    expect(currencySymbol("XXX")).toBe("₽");
    expect(currencySymbol("")).toBe("₽");
  });
});

describe("headlineSuffix", () => {
  it("emits 'symbol (code)' when symbol differs from code", () => {
    expect(headlineSuffix("RUB")).toBe("₽ (RUB)");
    expect(headlineSuffix("USD")).toBe("$ (USD)");
    expect(headlineSuffix("EUR")).toBe("€ (EUR)");
    expect(headlineSuffix("CNY")).toBe("¥ (CNY)");
    expect(headlineSuffix("TRY")).toBe("₺ (TRY)");
  });

  it("omits the redundant code annotation when symbol equals code (AED)", () => {
    expect(headlineSuffix("AED")).toBe("AED");
  });

  it("falls back to RUB headline for unknown codes", () => {
    expect(headlineSuffix("XYZ")).toBe("₽ (RUB)");
  });
});

describe("CURRENCIES table", () => {
  it("matches the Python set: RUB/USD/EUR/CNY/AED/TRY", () => {
    const codes = CURRENCIES.map((c) => c.code).sort();
    expect(codes).toEqual(["AED", "CNY", "EUR", "RUB", "TRY", "USD"]);
  });

  it("has a unique code for every entry", () => {
    const codes = CURRENCIES.map((c) => c.code);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it("currencyEntry returns frozen-style stable references", () => {
    const a = currencyEntry("USD");
    const b = currencyEntry("USD");
    expect(a).toBe(b);
  });
});
