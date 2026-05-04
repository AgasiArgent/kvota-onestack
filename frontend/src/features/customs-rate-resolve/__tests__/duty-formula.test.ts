import { describe, it, expect } from "vitest";

import { formatDutyFormula, formatRub } from "../lib/duty-formula";

/**
 * Pure-function tests for the Manual duty-rate live preview helper
 * (Phase A Req 4, Task 10).
 *
 * `Number.toLocaleString('ru-RU')` uses NBSP (U+00A0) as the thousand
 * separator on Node — matching the browser. Test assertions therefore use
 * NBSP explicitly.
 */

const NBSP = " ";

describe("formatRub", () => {
  it("uses NBSP thousand separator", () => {
    expect(formatRub(150_000)).toBe(`150${NBSP}000`);
  });

  it("limits to 2 decimal places", () => {
    expect(formatRub(123.456789)).toBe("123,46");
  });

  it("handles zero", () => {
    expect(formatRub(0)).toBe("0");
  });
});

describe("formatDutyFormula — simple percent", () => {
  it("renders ad-valorem rate against customs_value", () => {
    const out = formatDutyFormula({
      rate_type: "simple",
      value_1: 10,
      unit_1: "percent",
      customs_value: 150_000,
      weight_kg: null,
    });
    expect(out).toBe(`duty = 150${NBSP}000 × 10% = 15${NBSP}000 ₽`);
  });

  it("renders zero customs_value as 0 ₽", () => {
    const out = formatDutyFormula({
      rate_type: "simple",
      value_1: 5,
      unit_1: "percent",
      customs_value: 0,
      weight_kg: null,
    });
    expect(out).toBe("duty = 0 × 5% = 0 ₽");
  });
});

describe("formatDutyFormula — combined", () => {
  it("uses max() when sign is '>' (но не менее)", () => {
    // 10% of 150_000 = 15_000; weight 95.5 × 0.04 EUR × 95.5 RUB/EUR ~ 364.81
    const out = formatDutyFormula({
      rate_type: "combined",
      value_1: 10,
      unit_1: "percent",
      value_2: 0.04,
      unit_2: "EUR/kg",
      sign: ">",
      customs_value: 150_000,
      weight_kg: 95.5,
      currency_rate: 95.5,
    });
    // ad-valorem 15_000, specific ~364.81 → max = 15_000
    expect(out).toContain("max(");
    expect(out).toContain(`15${NBSP}000`);
    expect(out).toContain("₽");
  });

  it("picks the larger part when '>' (specific dominates)", () => {
    // 1% of small customs_value vs heavy specific
    const out = formatDutyFormula({
      rate_type: "combined",
      value_1: 1,
      unit_1: "percent",
      value_2: 5,
      unit_2: "EUR/kg",
      sign: ">",
      customs_value: 1_000,
      weight_kg: 100,
      currency_rate: 100,
    });
    // ad-valorem 10, specific 100 × 5 × 100 = 50_000 → max = 50_000
    expect(out).toContain(`50${NBSP}000`);
    expect(out).toContain("max(");
  });

  it("uses sum() when sign is '+' (плюс)", () => {
    const out = formatDutyFormula({
      rate_type: "combined",
      value_1: 10,
      unit_1: "percent",
      value_2: 0.04,
      unit_2: "EUR/kg",
      sign: "+",
      customs_value: 150_000,
      weight_kg: 100,
      currency_rate: 100,
    });
    // 15_000 + (100 × 0.04 × 100) = 15_000 + 400 = 15_400
    expect(out).toContain("sum(");
    expect(out).toContain(`15${NBSP}400`);
  });

  it("falls back to simple-rate rendering when slot 2 incomplete", () => {
    const out = formatDutyFormula({
      rate_type: "combined",
      value_1: 10,
      unit_1: "percent",
      value_2: null,
      unit_2: null,
      sign: null,
      customs_value: 150_000,
      weight_kg: 100,
    });
    // No max/sum — just simple percent
    expect(out).not.toContain("max");
    expect(out).not.toContain("sum");
    expect(out).toContain("10%");
  });
});

describe("formatDutyFormula — specific (per-kg)", () => {
  it("multiplies weight × rate × currency_rate", () => {
    // 100 kg × 0.04 EUR × 95.5 RUB/EUR = 382
    const out = formatDutyFormula({
      rate_type: "specific",
      value_1: 0.04,
      unit_1: "EUR/kg",
      customs_value: 150_000,
      weight_kg: 100,
      currency_rate: 95.5,
    });
    expect(out).toContain("0.04 EUR/kg");
    expect(out).toContain("382 ₽");
  });

  it("uses 0 weight as null safeguard", () => {
    const out = formatDutyFormula({
      rate_type: "specific",
      value_1: 0.04,
      unit_1: "EUR/kg",
      customs_value: 150_000,
      weight_kg: null,
      currency_rate: 95.5,
    });
    expect(out).toContain("= 0 ₽");
  });

  it("uses quantity for per-pc rates", () => {
    // 50 pcs × 2 USD × 95 = 9_500
    const out = formatDutyFormula({
      rate_type: "specific",
      value_1: 2,
      unit_1: "USD/pc",
      customs_value: 100_000,
      weight_kg: null,
      quantity: 50,
      currency_rate: 95,
    });
    expect(out).toContain(`9${NBSP}500 ₽`);
  });

  it("uses RUB/l with currency_rate=1", () => {
    // 200 (volume proxy) × 50 RUB × 1 = 10_000
    const out = formatDutyFormula({
      rate_type: "specific",
      value_1: 50,
      unit_1: "RUB/l",
      customs_value: 100_000,
      weight_kg: 200,
      currency_rate: null,
    });
    expect(out).toContain(`10${NBSP}000`);
  });
});

describe("formatDutyFormula — null safety", () => {
  it("returns em-dash when value_1 is null", () => {
    expect(
      formatDutyFormula({
        rate_type: "simple",
        value_1: null,
        unit_1: "percent",
        customs_value: 150_000,
        weight_kg: null,
      }),
    ).toBe("—");
  });

  it("returns em-dash when customs_value is null", () => {
    expect(
      formatDutyFormula({
        rate_type: "simple",
        value_1: 10,
        unit_1: "percent",
        customs_value: null,
        weight_kg: null,
      }),
    ).toBe("—");
  });
});

describe("formatDutyFormula — Russian thousand separators", () => {
  it("formats large customs_value with NBSP separator", () => {
    const out = formatDutyFormula({
      rate_type: "simple",
      value_1: 10,
      unit_1: "percent",
      customs_value: 1_500_000,
      weight_kg: null,
    });
    expect(out).toContain(`1${NBSP}500${NBSP}000`);
    expect(out).toContain(`150${NBSP}000`);
  });
});
