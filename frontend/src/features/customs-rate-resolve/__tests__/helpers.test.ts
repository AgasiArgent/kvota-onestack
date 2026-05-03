import { describe, it, expect } from "vitest";

import { humanizeAge } from "../ui/source-timestamp";
import { formatRate } from "../ui/rate-breakdown";
import { isValidTnvedCode } from "../ui/auto-resolve-button";
import { paymentTypeLabel } from "../model/types";

describe("humanizeAge", () => {
  const NOW = new Date("2026-05-03T12:00:00Z");

  it("returns 'только что' for sub-minute ages", () => {
    expect(humanizeAge("2026-05-03T11:59:30Z", NOW)).toBe("только что");
  });

  it("returns N мин. for sub-hour ages", () => {
    expect(humanizeAge("2026-05-03T11:55:00Z", NOW)).toBe("5 мин. назад");
  });

  it("returns N ч. for sub-day ages", () => {
    expect(humanizeAge("2026-05-03T09:00:00Z", NOW)).toBe("3 ч. назад");
  });

  it("returns N дн. for sub-month ages", () => {
    expect(humanizeAge("2026-05-01T12:00:00Z", NOW)).toBe("2 дн. назад");
  });

  it("returns absolute date for older entries", () => {
    const result = humanizeAge("2025-12-01T12:00:00Z", NOW);
    expect(result).toMatch(/2025/);
  });

  it("handles invalid timestamps gracefully", () => {
    expect(humanizeAge("not-a-date", NOW)).toBe("неизвестно");
  });
});

describe("formatRate", () => {
  it("prefers raw_value_string when available", () => {
    expect(
      formatRate({
        payment_type: "IMP",
        value_1_number: 10,
        value_1_unit: "percent",
        value_1_currency: null,
        value_2_number: null,
        value_2_unit: null,
        value_2_currency: null,
        sign_1: null,
        raw_value_string: "10%, но не менее 0.04 EUR/kg",
        calculated_amount_rub: null,
      })
    ).toBe("10%, но не менее 0.04 EUR/kg");
  });

  it("formats percent rates", () => {
    expect(
      formatRate({
        payment_type: "IMP",
        value_1_number: 5,
        value_1_unit: "percent",
        value_1_currency: null,
        value_2_number: null,
        value_2_unit: null,
        value_2_currency: null,
        sign_1: null,
        raw_value_string: null,
        calculated_amount_rub: null,
      })
    ).toBe("5%");
  });

  it("formats currency-per-unit rates", () => {
    expect(
      formatRate({
        payment_type: "IMP",
        value_1_number: 0.04,
        value_1_unit: "166",
        value_1_currency: "EUR",
        value_2_number: null,
        value_2_unit: null,
        value_2_currency: null,
        sign_1: null,
        raw_value_string: null,
        calculated_amount_rub: null,
      })
    ).toBe("0.04 EUR/166");
  });

  it("falls back to em-dash when no values present", () => {
    expect(
      formatRate({
        payment_type: "IMP",
        value_1_number: null,
        value_1_unit: null,
        value_1_currency: null,
        value_2_number: null,
        value_2_unit: null,
        value_2_currency: null,
        sign_1: null,
        raw_value_string: null,
        calculated_amount_rub: null,
      })
    ).toBe("—");
  });
});

describe("isValidTnvedCode", () => {
  it("accepts 10-digit codes", () => {
    expect(isValidTnvedCode("0123456789")).toBe(true);
    expect(isValidTnvedCode("8517120000")).toBe(true);
  });

  it("rejects shorter codes", () => {
    expect(isValidTnvedCode("12345")).toBe(false);
  });

  it("rejects longer codes", () => {
    expect(isValidTnvedCode("12345678901")).toBe(false);
  });

  it("rejects non-numeric content", () => {
    expect(isValidTnvedCode("abcdefghij")).toBe(false);
    expect(isValidTnvedCode("12345 6789")).toBe(false);
  });

  it("trims surrounding whitespace", () => {
    expect(isValidTnvedCode("  0123456789  ")).toBe(true);
  });
});

describe("paymentTypeLabel", () => {
  it("returns Russian label for known codes", () => {
    expect(paymentTypeLabel("IMP")).toBe("Пошлина");
    expect(paymentTypeLabel("NDS")).toBe("НДС");
    expect(paymentTypeLabel("AKC")).toBe("Акциз");
  });

  it("falls through to raw code for unknown payment types", () => {
    expect(paymentTypeLabel("UNKNOWN_TYPE")).toBe("UNKNOWN_TYPE");
  });
});
