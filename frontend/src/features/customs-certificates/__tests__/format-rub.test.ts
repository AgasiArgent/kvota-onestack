import { describe, expect, it } from "vitest";

import { formatRub } from "../lib/format-rub";

/**
 * Pure-function tests for the customs-certificates RUB formatter
 * (Phase B Task 6).
 *
 * Locale `ru-RU` uses NBSP (U+00A0) as the thousand separator on Node
 * (matching the browser). Test assertions therefore use NBSP explicitly
 * via the `NBSP` constant — copy-paste between the helper and the test
 * should never drift to a regular space.
 */

const NBSP = " ";

describe("formatRub — integers", () => {
  it("renders zero with the ₽ suffix", () => {
    expect(formatRub(0)).toBe(`0${NBSP}₽`);
  });

  it("renders a small integer without decimals", () => {
    expect(formatRub(150)).toBe(`150${NBSP}₽`);
  });

  it("uses NBSP between thousands", () => {
    expect(formatRub(12_500)).toBe(`12${NBSP}500${NBSP}₽`);
  });

  it("scales to multi-million inputs", () => {
    expect(formatRub(1_234_567)).toBe(`1${NBSP}234${NBSP}567${NBSP}₽`);
  });

  it("does NOT render decimals for integer inputs", () => {
    // Mockup convention: integer RUB → no decimals, kopeks only on fractions.
    const out = formatRub(150);
    expect(out).not.toContain(",");
  });
});

describe("formatRub — fractions", () => {
  it("renders kopeks with comma decimal separator", () => {
    expect(formatRub(999_999.99)).toBe(`999${NBSP}999,99${NBSP}₽`);
  });

  it("pads to exactly 2 decimal places", () => {
    // 12.5 → "12,50" — never "12,5".
    expect(formatRub(12.5)).toBe(`12,50${NBSP}₽`);
  });

  it("rounds to 2 decimal places (banker's rounding via Intl)", () => {
    // 0.005 → "0,01" rounded by Intl; we don't depend on a specific tie-break
    // direction here — only that it never overflows to "0,005".
    const out = formatRub(0.005);
    expect(out).toMatch(/^0,\d{2} ₽$/);
  });

  it("uses NBSP between thousand groups in fractional values", () => {
    // 12 500,99 ₽
    const out = formatRub(12_500.99);
    expect(out).toContain(`12${NBSP}500`);
    expect(out).toContain("99");
  });
});

describe("formatRub — non-finite guards", () => {
  it("returns '0 ₽' for NaN", () => {
    expect(formatRub(Number.NaN)).toBe(`0${NBSP}₽`);
  });

  it("returns '0 ₽' for positive Infinity", () => {
    expect(formatRub(Number.POSITIVE_INFINITY)).toBe(`0${NBSP}₽`);
  });

  it("returns '0 ₽' for negative Infinity", () => {
    expect(formatRub(Number.NEGATIVE_INFINITY)).toBe(`0${NBSP}₽`);
  });
});

describe("formatRub — separator audit", () => {
  it("uses ru-RU NBSP separators (not regular spaces or commas)", () => {
    const out = formatRub(1_000_000);
    // NBSP (U+00A0) — never a regular space, never a comma between thousands.
    expect(out).toContain(NBSP);
    // Reject the most likely drift: `","` between thousands.
    expect(out).not.toMatch(/^1,000,000/);
  });

  it("ends with the ₽ glyph after a NBSP", () => {
    const out = formatRub(42);
    expect(out.endsWith(`${NBSP}₽`)).toBe(true);
  });
});
