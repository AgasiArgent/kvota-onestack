/**
 * Unit tests for the «Антидемпинг» column helpers (Phase A Req 6, Task 9).
 *
 * Covers:
 *   - Column descriptor registered in CUSTOMS_AVAILABLE_COLUMNS
 *   - shortenDecisionRef formatting rules (Решение N КТС / fallback / empty)
 *   - readSpecialDutyVariant priority + multiple snapshot shapes
 *   - buildSpecialDutyTooltip multi-line composition with order_ref + legal_link
 *
 * The renderer itself is DOM-bound and exercised via integration / browser
 * tests; this file unit-tests the data plumbing it relies on.
 */

import { describe, it, expect } from "vitest";

import {
  CUSTOMS_AVAILABLE_COLUMNS,
  type CustomsColumnSpec,
} from "../customs-columns";
import {
  shortenDecisionRef,
  readSpecialDutyVariant,
  buildSpecialDutyTooltip,
  type SpecialDutyVariant,
} from "../customs-handsontable";

describe("CUSTOMS_AVAILABLE_COLUMNS — customs_antidumping registration", () => {
  it("includes the customs_antidumping column with correct label", () => {
    const found = CUSTOMS_AVAILABLE_COLUMNS.find(
      (c: CustomsColumnSpec) => c.key === "customs_antidumping",
    );
    expect(found).toBeDefined();
    expect(found?.label).toBe("Антидемпинг");
  });

  it("places customs_antidumping after customs_excise and before customs_psm_pts", () => {
    const keys = CUSTOMS_AVAILABLE_COLUMNS.map((c) => c.key);
    const exciseIdx = keys.indexOf("customs_excise");
    const antidempIdx = keys.indexOf("customs_antidumping");
    const psmIdx = keys.indexOf("customs_psm_pts");
    expect(exciseIdx).toBeGreaterThanOrEqual(0);
    expect(psmIdx).toBeGreaterThanOrEqual(0);
    expect(antidempIdx).toBe(exciseIdx + 1);
    expect(antidempIdx).toBeLessThan(psmIdx);
  });
});

describe("shortenDecisionRef", () => {
  it("returns empty string for null / undefined / empty input", () => {
    expect(shortenDecisionRef(null)).toBe("");
    expect(shortenDecisionRef(undefined)).toBe("");
    expect(shortenDecisionRef("")).toBe("");
  });

  it("extracts decision number from canonical КТС reference", () => {
    expect(
      shortenDecisionRef(
        "Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины на стальные трубы из Украины)",
      ),
    ).toBe("Реш.702 КТС");
  });

  it("matches case-insensitively for КТС", () => {
    expect(shortenDecisionRef("решение 130 от 14.04.2010 ктс")).toBe(
      "Реш.130 КТС",
    );
  });

  it("falls back to truncation with ellipsis for non-КТС long text", () => {
    const long = "Постановление Правительства РФ № 688 от 30.06.2015";
    const result = shortenDecisionRef(long);
    expect(result).toHaveLength(19);
    expect(result.endsWith("…")).toBe(true);
    expect(result.startsWith("Постановление")).toBe(true);
  });

  it("returns short non-КТС strings unchanged", () => {
    expect(shortenDecisionRef("реш.80")).toBe("реш.80");
    expect(shortenDecisionRef("Short ref")).toBe("Short ref");
  });

  it("returns string of exactly 20 chars unchanged (boundary)", () => {
    const exactly20 = "A".repeat(20);
    expect(shortenDecisionRef(exactly20)).toBe(exactly20);
  });
});

describe("readSpecialDutyVariant", () => {
  it("returns null when item has no snapshot fields at all", () => {
    expect(readSpecialDutyVariant({})).toBeNull();
  });

  it("returns null when customs_rates_snapshot exists but has no IMPDEMP/IMPCOMP/IMPDOP/IMPTMP variant", () => {
    const item = {
      customs_rates_snapshot: {
        rates: [
          { payment_type: "IMP", value_1_number: 10 },
          { payment_type: "NDS", value_1_number: 22 },
        ],
      },
    };
    expect(readSpecialDutyVariant(item)).toBeNull();
  });

  it("reads IMPDEMP variant from customs_rates_snapshot.rates (Phase 1 shape)", () => {
    const item = {
      customs_rates_snapshot: {
        rates: [
          { payment_type: "IMP", value_1_number: 10 },
          {
            payment_type: "IMPDEMP",
            value_1_number: 18.9,
            order_ref:
              "Решение 702 от 22.06.2011 КТС (Антидемпинговые пошлины на стальные трубы из Украины)",
            legal_link: "https://alta.ru/tamdoc/11sr0702/",
          },
          { payment_type: "NDS", value_1_number: 22 },
        ],
      },
    };
    const variant = readSpecialDutyVariant(item);
    expect(variant).not.toBeNull();
    expect(variant?.payment_type).toBe("IMPDEMP");
    expect(variant?.value_1_number).toBe(18.9);
    expect(variant?.order_ref).toContain("Решение 702");
    expect(variant?.legal_link).toBe("https://alta.ru/tamdoc/11sr0702/");
  });

  it("prefers IMPDEMP over IMPCOMP / IMPDOP / IMPTMP when multiple present", () => {
    const item = {
      customs_rates_snapshot: {
        rates: [
          { payment_type: "IMPCOMP", value_1_number: 5 },
          { payment_type: "IMPDOP", value_1_number: 7 },
          { payment_type: "IMPDEMP", value_1_number: 20, order_ref: "Реш.702 КТС" },
          { payment_type: "IMPTMP", value_1_number: 3 },
        ],
      },
    };
    const variant = readSpecialDutyVariant(item);
    expect(variant?.payment_type).toBe("IMPDEMP");
    expect(variant?.value_1_number).toBe(20);
  });

  it("falls through to IMPCOMP when no IMPDEMP", () => {
    const item = {
      customs_rates_snapshot: {
        rates: [
          { payment_type: "IMPCOMP", value_1_number: 5, order_ref: null },
          { payment_type: "IMPTMP", value_1_number: 3 },
        ],
      },
    };
    const variant = readSpecialDutyVariant(item);
    expect(variant?.payment_type).toBe("IMPCOMP");
    expect(variant?.value_1_number).toBe(5);
    expect(variant?.order_ref).toBeNull();
  });

  it("reads IMPDEMP from _resolved_rates_by_payment_type (Phase A live shape)", () => {
    const item = {
      _resolved_rates_by_payment_type: {
        IMPDEMP: [
          {
            value_1_number: 12.5,
            order_ref: "Решение 130 от 14.04.2010 КТС",
            legal_link: "https://alta.ru/tamdoc/10sr0130/",
          },
        ],
      },
    };
    const variant = readSpecialDutyVariant(item);
    expect(variant?.payment_type).toBe("IMPDEMP");
    expect(variant?.value_1_number).toBe(12.5);
    expect(variant?.order_ref).toContain("Решение 130");
  });

  it("reads IMPDEMP from tnved_user_choices_chosen (Phase A user-choice shape)", () => {
    const item = {
      tnved_user_choices_chosen: {
        chosen_impdemp_variant: {
          value_1_number: 9.7,
          order_ref: "Решение 702 КТС",
          legal_link: null,
        },
        chosen_impcomp_variant: null,
      },
    };
    const variant = readSpecialDutyVariant(item);
    expect(variant?.payment_type).toBe("IMPDEMP");
    expect(variant?.value_1_number).toBe(9.7);
    expect(variant?.legal_link).toBeNull();
  });

  it("ignores variant when value_1_number is missing or non-numeric", () => {
    const item = {
      customs_rates_snapshot: {
        rates: [
          { payment_type: "IMPDEMP", order_ref: "no value" },
          { payment_type: "IMPCOMP", value_1_number: "5" },
        ],
      },
    };
    expect(readSpecialDutyVariant(item)).toBeNull();
  });

  it("normalises empty order_ref / legal_link to null", () => {
    const item = {
      customs_rates_snapshot: {
        rates: [
          {
            payment_type: "IMPDEMP",
            value_1_number: 18,
            order_ref: "",
            legal_link: "",
          },
        ],
      },
    };
    const variant = readSpecialDutyVariant(item);
    expect(variant?.order_ref).toBeNull();
    expect(variant?.legal_link).toBeNull();
  });

  it("prefers customs_rates_snapshot over _resolved_rates_by_payment_type when both present", () => {
    const item = {
      customs_rates_snapshot: {
        rates: [
          {
            payment_type: "IMPDEMP",
            value_1_number: 18,
            order_ref: "from snapshot",
          },
        ],
      },
      _resolved_rates_by_payment_type: {
        IMPDEMP: [{ value_1_number: 99, order_ref: "from live" }],
      },
    };
    const variant = readSpecialDutyVariant(item);
    expect(variant?.value_1_number).toBe(18);
    expect(variant?.order_ref).toBe("from snapshot");
  });
});

describe("buildSpecialDutyTooltip", () => {
  it("renders three-line tooltip when both order_ref and legal_link present (IMPDEMP)", () => {
    const variant: SpecialDutyVariant = {
      payment_type: "IMPDEMP",
      value_1_number: 18.9,
      order_ref: "Решение 702 от 22.06.2011 КТС",
      legal_link: "https://alta.ru/tamdoc/11sr0702/",
    };
    const tooltip = buildSpecialDutyTooltip(variant);
    expect(tooltip).toBe(
      "Антидемпинговая пошлина\nРешение 702 от 22.06.2011 КТС\nhttps://alta.ru/tamdoc/11sr0702/",
    );
  });

  it("renders only label and order_ref when legal_link missing", () => {
    const variant: SpecialDutyVariant = {
      payment_type: "IMPCOMP",
      value_1_number: 5,
      order_ref: "Реш.130 КТС",
      legal_link: null,
    };
    const tooltip = buildSpecialDutyTooltip(variant);
    expect(tooltip).toBe("Компенсационная пошлина\nРеш.130 КТС");
  });

  it("renders label only when both metadata fields missing", () => {
    const variant: SpecialDutyVariant = {
      payment_type: "IMPTMP",
      value_1_number: 3,
      order_ref: null,
      legal_link: null,
    };
    expect(buildSpecialDutyTooltip(variant)).toBe("Сезонная пошлина");
  });

  it("uses correct Russian label for each payment_type", () => {
    const types: Array<SpecialDutyVariant["payment_type"]> = [
      "IMPDEMP",
      "IMPCOMP",
      "IMPDOP",
      "IMPTMP",
    ];
    const expected = [
      "Антидемпинговая пошлина",
      "Компенсационная пошлина",
      "Специальная защитная пошлина",
      "Сезонная пошлина",
    ];
    types.forEach((t, i) => {
      const tip = buildSpecialDutyTooltip({
        payment_type: t,
        value_1_number: 1,
      });
      expect(tip).toBe(expected[i]);
    });
  });
});
