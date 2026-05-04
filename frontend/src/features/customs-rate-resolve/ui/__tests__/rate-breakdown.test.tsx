import React from "react";
import { renderToString } from "react-dom/server";
import { describe, it, expect } from "vitest";

import {
  RateBreakdown,
  composeNdsFormula,
  composeNdsTooltip,
  type TotalContext,
} from "../rate-breakdown";
import type { ResolvedRate } from "../../model/types";

/**
 * The frontend workspace does not ship `@testing-library/react` or a DOM
 * environment (no jsdom). We follow the same pattern as
 * `shared/ui/geo/__tests__/country-combobox.test.tsx`:
 *
 *   1. React's server renderer (`react-dom/server`) — asserts the markup
 *      contains the expected formula text and attributes.
 *   2. Pure helpers exported from the component module
 *      (`composeNdsFormula`, `composeNdsTooltip`) — carry the formula and
 *      tooltip composition logic, testable without a DOM.
 *
 * NOTE: `Number.toLocaleString('ru-RU')` uses NBSP (U+00A0) as the thousand
 * separator on Node — the same character ships to the browser. Test
 * assertions use ` ` explicitly to match exactly.
 */

const NBSP = " ";

const VARIANT_DEFAULTS = {
  description: null,
  category_code: null,
  category_ru: null,
  condition_text: null,
  legal_document: null,
  legal_link: null,
  order_ref: null,
  is_default: false,
} as const;

function _rate(overrides: Partial<ResolvedRate>): ResolvedRate {
  return {
    payment_type: "NDS",
    value_1_number: null,
    value_1_unit: null,
    value_1_currency: null,
    value_2_number: null,
    value_2_unit: null,
    value_2_currency: null,
    sign_1: null,
    raw_value_string: null,
    calculated_amount_rub: null,
    ...VARIANT_DEFAULTS,
    ...overrides,
  };
}

// ============================================================================
// composeNdsFormula — pure helper
// ============================================================================

describe("composeNdsFormula", () => {
  const ctx: TotalContext = {
    customs_value_rub: 150000,
    total_import_duty_rub: 15000,
    akc_rub: 0,
  };

  it("composes formula with real numbers and ru-RU separators", () => {
    const variant = _rate({
      payment_type: "NDS",
      value_1_number: 22,
      value_1_unit: "percent",
      is_default: true,
    });
    const formula = composeNdsFormula(ctx, variant);
    expect(formula).toBe(
      `(150${NBSP}000 + 15${NBSP}000 + 0) × 22% = 36${NBSP}300`,
    );
  });

  it("formats large customs_value with Russian thousand separators", () => {
    const bigCtx: TotalContext = {
      customs_value_rub: 1000000,
      total_import_duty_rub: 0,
      akc_rub: 0,
    };
    const variant = _rate({
      payment_type: "NDS",
      value_1_number: 22,
      value_1_unit: "percent",
    });
    const formula = composeNdsFormula(bigCtx, variant);
    expect(formula).toContain(`1${NBSP}000${NBSP}000`);
  });

  it("returns null for non-percent variants (raw_value_string-only)", () => {
    const variant = _rate({
      payment_type: "NDS",
      value_1_number: null,
      value_1_unit: null,
      raw_value_string: "specific льгота",
    });
    expect(composeNdsFormula(ctx, variant)).toBeNull();
  });

  it("supports льготные rates (10% / 0%)", () => {
    const lecr = _rate({
      payment_type: "NDS",
      value_1_number: 10,
      value_1_unit: "percent",
      category_ru: "Медтехника с регуд",
    });
    const formula = composeNdsFormula(ctx, lecr);
    expect(formula).toBe(
      `(150${NBSP}000 + 15${NBSP}000 + 0) × 10% = 16${NBSP}500`,
    );
  });
});

// ============================================================================
// composeNdsTooltip — pure helper
// ============================================================================

describe("composeNdsTooltip", () => {
  it("enumerates non-selected льготные variants", () => {
    const variants: ResolvedRate[] = [
      _rate({
        payment_type: "NDS",
        value_1_number: 22,
        value_1_unit: "percent",
        category_ru: "Прочие",
        is_default: true,
      }),
      _rate({
        payment_type: "NDS",
        value_1_number: 10,
        value_1_unit: "percent",
        category_ru: "Медтехника",
        condition_text: "с регистрационным удостоверением",
      }),
      _rate({
        payment_type: "NDS",
        value_1_number: 0,
        value_1_unit: "percent",
        category_ru: "Для инвалидов",
      }),
    ];
    const tooltip = composeNdsTooltip(variants, 0);
    expect(tooltip).not.toBeNull();
    expect(tooltip).toContain(
      "Медтехника (с регистрационным удостоверением): 10%",
    );
    expect(tooltip).toContain("Для инвалидов: 0%");
    // Selected (idx=0) is NOT included.
    expect(tooltip).not.toContain("Прочие");
  });

  it("returns null when only one variant present", () => {
    const variants: ResolvedRate[] = [
      _rate({
        payment_type: "NDS",
        value_1_number: 22,
        value_1_unit: "percent",
        category_ru: "Прочие",
      }),
    ];
    expect(composeNdsTooltip(variants, 0)).toBeNull();
  });

  it("falls back to 'Вариант' when category_ru missing", () => {
    const variants: ResolvedRate[] = [
      _rate({
        payment_type: "NDS",
        value_1_number: 22,
        value_1_unit: "percent",
      }),
      _rate({
        payment_type: "NDS",
        value_1_number: 10,
        value_1_unit: "percent",
      }),
    ];
    const tooltip = composeNdsTooltip(variants, 0);
    expect(tooltip).toContain("Вариант: 10%");
  });
});

// ============================================================================
// RateBreakdown — SSR rendering
// ============================================================================

describe("RateBreakdown — NDS formula display (Req 7)", () => {
  const NDS_DEFAULT = _rate({
    payment_type: "NDS",
    value_1_number: 22,
    value_1_unit: "percent",
    category_ru: "Прочие",
    is_default: true,
  });

  it("renders NDS formula with real numbers when totalContext provided", () => {
    const ctx: TotalContext = {
      customs_value_rub: 150000,
      total_import_duty_rub: 15000,
      akc_rub: 0,
    };
    const html = renderToString(
      <RateBreakdown
        rates={[NDS_DEFAULT]}
        totalRub={null}
        source="alta-live"
        totalContext={ctx}
      />,
    );
    expect(html).toContain(`(150${NBSP}000 + 15${NBSP}000 + 0) × 22% = 36${NBSP}300`);
    // Monospace amber styling per design spec.
    expect(html).toContain("font-mono");
    expect(html).toContain("text-amber-400");
  });

  it("falls back to simple '22%' rendering when totalContext absent", () => {
    const html = renderToString(
      <RateBreakdown
        rates={[NDS_DEFAULT]}
        totalRub={null}
        source="alta-live"
      />,
    );
    expect(html).toContain("22%");
    // No formula box — formula text uses '×' which only the formula emits.
    expect(html).not.toContain("× 22% =");
    expect(html).not.toContain("text-amber-400");
  });

  it("falls back to simple rendering when totalContext is null", () => {
    const html = renderToString(
      <RateBreakdown
        rates={[NDS_DEFAULT]}
        totalRub={null}
        source="alta-live"
        totalContext={null}
      />,
    );
    expect(html).toContain("22%");
    expect(html).not.toContain("× 22% =");
  });

  it("formats Russian thousand separators in formula", () => {
    const ctx: TotalContext = {
      customs_value_rub: 1000000,
      total_import_duty_rub: 100000,
      akc_rub: 0,
    };
    const html = renderToString(
      <RateBreakdown
        rates={[NDS_DEFAULT]}
        totalRub={null}
        source="alta-live"
        totalContext={ctx}
      />,
    );
    expect(html).toContain(`1${NBSP}000${NBSP}000`);
    expect(html).toContain(`100${NBSP}000`);
  });

  it("tooltip enumerates льготные variants when multiple NDS categories", () => {
    const variants: ResolvedRate[] = [
      NDS_DEFAULT,
      _rate({
        payment_type: "NDS",
        value_1_number: 10,
        value_1_unit: "percent",
        category_ru: "Медтехника",
        condition_text: "с регуд",
      }),
      _rate({
        payment_type: "NDS",
        value_1_number: 0,
        value_1_unit: "percent",
        category_ru: "Для инвалидов",
      }),
    ];
    const html = renderToString(
      <RateBreakdown
        rates={variants}
        totalRub={null}
        source="alta-live"
      />,
    );
    // The title attribute is HTML-escaped — & becomes &amp;, but our chars
    // are safe. Newlines inside `title=` get encoded; we assert on the
    // escaped form that `renderToString` emits.
    // React renders `\n` as `\n` inside the attribute value (no encoding) —
    // assert presence of both alternatives.
    expect(html).toContain("Медтехника (с регуд): 10%");
    expect(html).toContain("Для инвалидов: 0%");
  });

  it("renders 'Ставки не найдены' when rates empty", () => {
    const html = renderToString(
      <RateBreakdown rates={[]} totalRub={null} source="alta-live" />,
    );
    expect(html).toContain("Ставки не найдены");
  });

  it("does not emit formula for non-NDS payment_types", () => {
    const ctx: TotalContext = {
      customs_value_rub: 150000,
      total_import_duty_rub: 15000,
      akc_rub: 0,
    };
    const impRate = _rate({
      payment_type: "IMP",
      value_1_number: 10,
      value_1_unit: "percent",
    });
    const html = renderToString(
      <RateBreakdown
        rates={[impRate]}
        totalRub={null}
        source="alta-live"
        totalContext={ctx}
      />,
    );
    expect(html).not.toContain("× 10% =");
    expect(html).not.toContain("text-amber-400");
  });
});
